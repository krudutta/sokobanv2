
# coding: utf-8

# In[1]:


import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torch.autograd as autograd

from common.multiprocessing_env import SubprocVecEnv
from common.sokoban_env import SokobanEnv

USE_CUDA = torch.cuda.is_available()
Variable = lambda *args, **kwargs: autograd.Variable(*args, **kwargs).cuda() if USE_CUDA else autograd.Variable(*args, **kwargs)


# In[2]:


class OnPolicy(nn.Module):
    def __init__(self):
        super(OnPolicy, self).__init__()
        
    def forward(self, x):
        raise NotImplementedError
        
    def act(self, x, deterministic=False):
        logit, value = self.forward(x)
        probs = F.softmax(logit)
        
        if deterministic:
            action = probs.max(1)[1]
        else:
            action = probs.multinomial(1)
        
        return action
    
    def evaluate_actions(self, x, action):
        logit, value = self.forward(x)
        
        probs     = F.softmax(logit)
        log_probs = F.log_softmax(logit)
        
        action_log_probs = log_probs.gather(1, action)
        entropy = -(probs * log_probs).sum(1).mean()
        
        return logit, action_log_probs, value, entropy

class ActorCritic(OnPolicy):
    def __init__(self, in_shape, num_actions):
        super(ActorCritic, self).__init__()
        
        self.in_shape = in_shape
        
        self.features = nn.Sequential(
            nn.Conv2d(in_shape[0], 32, kernel_size=4, stride=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, stride=1),
            nn.ReLU(),
        )
        
        self.fc = nn.Sequential(
            nn.Linear(self.feature_size(), 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
        )
        
        self.critic  = nn.Linear(64, 1)
        self.actor   = nn.Linear(64, num_actions)
        
    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        logit = self.actor(x)
        value = self.critic(x)
        return logit, value
    
    def feature_size(self):
        return self.features(autograd.Variable(torch.zeros(1, *self.in_shape))).view(1, -1).size(1)

class RolloutStorage(object):
    def __init__(self, num_steps, num_envs, state_shape):
        self.num_steps = num_steps
        self.num_envs  = num_envs
        self.states  = torch.zeros(num_steps + 1, num_envs, *state_shape)
        self.rewards = torch.zeros(num_steps,     num_envs, 1)
        self.masks   = torch.ones(num_steps  + 1, num_envs, 1)
        self.actions = torch.zeros(num_steps,     num_envs, 1).long()
        self.use_cuda = False
            
    def cuda(self):
        self.use_cuda  = True
        self.states    = self.states.cuda()
        self.rewards   = self.rewards.cuda()
        self.masks     = self.masks.cuda()
        self.actions   = self.actions.cuda()
        
    def insert(self, step, state, action, reward, mask):
        self.states[step + 1].copy_(state)
        self.actions[step].copy_(action)
        self.rewards[step].copy_(reward)
        self.masks[step + 1].copy_(mask)
        
    def after_update(self):
        self.states[0].copy_(self.states[-1])
        self.masks[0].copy_(self.masks[-1])
        
    def compute_returns(self, next_value, gamma):
        returns   = torch.zeros(self.num_steps + 1, self.num_envs, 1)
        if self.use_cuda:
            returns = returns.cuda()
        returns[-1] = next_value
        for step in reversed(range(self.num_steps)):
            returns[step] = returns[step + 1] * gamma * self.masks[step + 1] + self.rewards[step]
        return returns[:-1]


# In[ ]:


num_envs = 4

def make_env():
    def _thunk():
        env = SokobanEnv()
        return env

    return _thunk

envs = [make_env() for i in range(num_envs)]
envs = SubprocVecEnv(envs)

state_shape = envs.observation_space.shape

#a2c hyperparams:
gamma = 0.99
entropy_coef = 0.01
value_loss_coef = 0.5
max_grad_norm = 0.5
num_steps = 120
num_batch = int(10e5)

#rmsprop hyperparams:
lr    = 7e-4
eps   = 1e-5
alpha = 0.99

#Init a2c and rmsprop
actor_critic = ActorCritic(envs.observation_space.shape, envs.action_space.n)
optimizer = optim.RMSprop(actor_critic.parameters(), lr, eps=eps, alpha=alpha)
    
if USE_CUDA:
    actor_critic = actor_critic.cuda()

rollout = RolloutStorage(num_steps, num_envs, envs.observation_space.shape)
# rollout.cuda()

all_rewards = []
all_losses  = []

state = envs.reset()
state = torch.FloatTensor(np.float32(state))

rollout.states[0].copy_(state)

episode_rewards = torch.zeros(num_envs, 1)
final_rewards   = torch.zeros(num_envs, 1)

for i_update in range(num_batch):

    for step in range(num_steps):
        action = actor_critic.act(Variable(state))
        next_state, reward, done, _ = envs.step(action.squeeze(1).cpu().data.numpy())

        reward = torch.FloatTensor(reward).unsqueeze(1)
        episode_rewards += reward
        masks = torch.FloatTensor(1-np.array(done)).unsqueeze(1)
        final_rewards *= masks
        final_rewards += (1-masks) * episode_rewards
        episode_rewards *= masks

        if USE_CUDA:
            masks = masks.cuda()

        state = torch.FloatTensor(np.float32(next_state))
        rollout.insert(step, state, action.data, reward, masks)


    _, next_value = actor_critic(Variable(rollout.states[-1], requires_grad=True))
    with torch.no_grad():
        next_value = next_value.data

    returns = rollout.compute_returns(next_value, gamma)

    logit, action_log_probs, values, entropy = actor_critic.evaluate_actions(
        Variable(rollout.states[:-1]).view(-1, *state_shape),
        Variable(rollout.actions).view(-1, 1)
    )

    values = values.view(num_steps, num_envs, 1)
    action_log_probs = action_log_probs.view(num_steps, num_envs, 1)
    advantages = Variable(returns) - values

    value_loss = advantages.pow(2).mean()
    action_loss = -(Variable(advantages.data) * action_log_probs).mean()

    optimizer.zero_grad()
    loss = value_loss * value_loss_coef + action_loss - entropy * entropy_coef
    loss.backward()
    nn.utils.clip_grad_norm(actor_critic.parameters(), max_grad_norm)
    optimizer.step()
    
    if i_update % 100 == 0:
        all_rewards.append(final_rewards.mean())
        all_losses.append(loss.data[0])
        print("REWARDS=> MEAN: "+str(final_rewards.mean())+" MAX: "+str(final_rewards.max())+" MEDIAN: "+str(final_rewards.median()))
        
        
    rollout.after_update()
    

# save model
torch.save(actor_critic.state_dict(), "actor_critic_")

