import numpy as np
import random
import copy
import gym
import os
__path__=[os.path.dirname(os.path.abspath(__file__))]
from . import level_generator
from gym import error, spaces, utils

WORLD_DIM = 10
NUM_BOX = 2

class SokobanEnv(gym.Env):
    metadata = {'render.modes': ['human']}
    """ This gym implements a simple Sokoban environment. """
    
    def __init__(self):
        
        # general variables
        self.MAX_STEPS = 120
        self.curr_step = -1
        self.player_pos = (-1,-1)
        self.is_finish = False
        self.world = None
        self.past_world = None
        
        # action and observation spaces
        self._action_set = [1, 2, 3, 4]
        self.action_space = spaces.Discrete(len(self._action_set))
        self.observation_space = None
        
        
    def step(self, a):
        action = self._action_set[a]
        if self.is_finish:
            raise RuntimeError("Episode is done")
        self.curr_step += 1
        self._take_action(action)
        reward = self._get_reward()
        observation = self._get_state()
        info = self.world
        if self.curr_step == self.MAX_STEPS:
            self.is_finish = True
        return observation, reward, self.is_finish, info
    
    def reset(self):
        #function to reset the environment to a new room configuration
        self.world, self.player_pos = level_generator.level_generator(WORLD_DIM, WORLD_DIM, NUM_BOX)
        self.size = np.shape(self.world)
        self.is_finish = False
        self.curr_step = -1
        oS = self.size[0]*self.size[1]*4
        self.observation_space = spaces.Discrete(oS)
        
        return self._get_state()
    
    def set_level(self, world, positions):
        self.world = world
        self.player_pos = positions
        self.size = np.shape(self.world)
        self.is_finish = False
        self.curr_step = -1
        oS = self.size[0]*self.size[1]*4
        self.observation_space = spaces.Discrete(oS)
        
    
    def render(self, mode='human', close=False):
        #function to visualise the problem
#         root.mainloop()
#         time.sleep(2) 
#         root.quit()
    
    def _move_y(self, x, y, aux=None, option=1):
        # move the player in left/right direction
        if option == 2 and aux != None: #encountered a box
            op = self._get_opt(x,aux)
            if op == 1 or op == 2 or op == 5: #encountered a box or a wall at auxilliary position
                pass
            elif op == 3: #encountered an empty tile at auxilliary position
                self._update_player()
                self.world[aux,x] = 'B'
                self.world[y,x] = 'P'
                self.player_pos = (x,y)
            elif op == 4: #encountered a target tile at auxilliary position
                self._update_player()
                self.world[aux,x] = 'C'
                self.world[y,x] = 'P'
                self.player_pos = (x,y)
        elif option == 3 and aux == None: #encountered an empty tile
            self._update_player()
            self.world[y,x] = 'P'
            self.player_pos = (x,y)
        elif option == 4 and aux == None: #encountered a target tile
            self._update_player()
            self.world[y,x] = 'X'
            self.player_pos = (x,y)
        elif option == 5 and aux!=None: #encountered a box kept on a target tile
            op = self._get_opt(x,aux)
            if op == 1 or op == 2 or op == 5: #encountered a box or a wall at auxilliary position
                pass
            elif op == 3: #encountered an empty tile at auxilliary position
                self._update_player()
                self.world[aux,x] = 'B'
                self.world[y,x] = 'X'
                self.player_pos = (x,y)
            elif op == 4: #encountered a target tile at auxilliary position
                self._update_player()
                self.world[aux,x] = 'C'
                self.world[y,x] = 'X'
                self.player_pos = (x,y)
    
    def _move_x(self, x, y, aux=None, option=1):
        # move the player in left/right direction
        if option == 2 and aux != None: #encountered a box
            op = self._get_opt(aux,y)
            if op == 1 or op == 2 or op == 5: #encountered a box or a wall at auxilliary position
                pass
            elif op == 3: #encountered an empty tile at auxilliary position
                self._update_player()
                self.world[y,aux] = 'B'
                self.world[y,x] = 'P'
                self.player_pos = (x,y)
            elif op == 4: #encountered a target tile at auxilliary position
                self._update_player()
                self.world[y,aux] = 'C'
                self.world[y,x] = 'P'
                self.player_pos = (x,y)
        elif option == 3 and aux == None: #encountered an empty tile
            self._update_player()
            self.world[y,x] = 'P'
            self.player_pos = (x,y)
        elif option == 4 and aux == None: #encountered a target tile
            self._update_player()
            self.world[y,x] = 'X'
            self.player_pos = (x,y)
        elif option == 5 and aux != None: #encountered a box kept on a target tile
            op = self._get_opt(aux,y)
            if op == 1 or op == 2 or op == 5: #encountered a box or a wall at auxilliary position
                pass
            elif op == 3: #encountered an empty tile at auxilliary position
                self._update_player()
                self.world[y,aux] = 'B'
                self.world[y,x] = 'X'
                self.player_pos = (x,y)
            elif op == 4: #encountered a target tile at auxilliary position
                self._update_player()
                self.world[y,aux] = 'C'
                self.world[y,x] = 'X'
                self.player_pos = (x,y)
    
    def _update_player(self):
        # update the player position
        x, y = self.player_pos
        if self.world[y,x] == 'P': #pure player tile
            self.world[y,x] = 'E'
        elif self.world[y,x] == 'X': #player standing on a target tile
            self.world[y,x] = 'T'
    
    def _get_opt(self,x,y):
        # for any action, return the code for the next tile encountered
        if self.world[y,x] == 'W':  #encounters a wall at (x,y)
            return 1
        elif self.world[y,x] == 'B': #encounters  a box at (x,y)
            return 2
        elif self.world[y,x] == 'E': #encounters an empty tile at (x,y)
            return 3
        elif self.world[y,x] == 'T': #encounters a target tile at (x,y)
            return 4
        elif self.world[y,x] == 'C': #encounters a box kept on a target tile at (x,y)
            return 5
        else:
            raise RuntimeError("Invalid Box")
    
    def _take_action(self, action):
        # change the matrix representation according to the action specified
        self.past_world = copy.deepcopy(self.world)
        new_x, new_y = self.player_pos
        # MOVE LEFT
        if action == 1:
            new_x = new_x-1
            opt = self._get_opt(new_x, new_y)
            if opt == 2 or opt == 5: #encountered a box, do a push-ahead mechanism
                x2 = new_x-1
                self._move_x(new_x, new_y, aux=x2, option=opt)
            elif opt == 3 or opt == 4: #encountered an empty tile or a target tile
                self._move_x(new_x, new_y, option=opt)
        # MOVE RIGHT
        elif action == 2:
            new_x = new_x+1
            opt = self._get_opt(new_x, new_y)
            if opt == 2 or opt == 5: #encountered a box, do a push-ahead mechanism
                x2 = new_x+1
                self._move_x(new_x, new_y, aux=x2, option=opt)
            elif opt == 3 or opt == 4: #encountered an empty tile or a target tile
                self._move_x(new_x, new_y, option=opt)
        # MOVE UP
        elif action == 3:
            new_y = new_y-1
            opt = self._get_opt(new_x, new_y)
            if opt == 2 or opt == 5: #encountered a box, do a push-ahead mechanism
                y2 = new_y-1
                self._move_y(new_x, new_y, aux=y2, option=opt)
            elif opt == 3 or opt == 4: #encountered an empty tile or a target tile
                self._move_y(new_x, new_y, option=opt)
        # MOVE DOWN
        elif action == 4:
            new_y = new_y+1
            opt = self._get_opt(new_x, new_y)
            if opt == 2 or opt == 5: #encountered a box, do a push-ahead mechanism
                y2 = new_y+1
                self._move_y(new_x, new_y, aux=y2, option=opt)
            elif opt == 3 or opt == 4: #encountered an empty tile or a target tile
                self._move_y(new_x, new_y, option=opt)
    
    def _check_state(self):
        # return integer associated with reward/punishment states after comparing current and previous states
        unique_p, counts_p = np.unique(self.past_world, return_counts=True)
        unique_c, counts_c = np.unique(self.world, return_counts=True)
        info_p = dict(zip(unique_p, counts_p))
        info_c = dict(zip(unique_c, counts_c))
        p_T=0
        c_T=0
        p_X=0
        c_X=0
        p_C=0
        c_C=0
        if 'X' in info_c.keys():
            c_X = info_c['X']
        if 'X' in info_p.keys():
            p_X = info_p['X']
            
        if 'T' in info_c.keys():
            c_T = info_c['T']
        if 'T' in info_p.keys():
            p_T = info_p['T']
            
        if 'C' in info_c.keys():
            c_C = info_c['C']
        if 'C' in info_p.keys():
            p_C = info_p['C']
        
        if c_C == NUM_BOX:
            self.is_finish = True
            return 1
        
        if p_C > c_C:
            return 3
        
        if p_C < c_C:
            return 2
        
        if (p_X + p_T) == (c_X + c_T):
            return 4
        
        return -1
    
    def _get_state(self):
        # return the current state observation
        s = self.size[0]
        rgb = np.full((s,s,3), 0)
        for i in range(0,s):
            for j in range(0,s):
                if self.world[i,j] == 'W':
                    rgb[i,j] = [0,0,0]
                elif self.world[i,j] == 'E':
                    rgb[i,j] = [255,255,255]
                elif self.world[i,j] == 'T':
                    rgb[i,j] = [255,0,0]
                elif self.world[i,j] == 'B':
                    rgb[i,j] = [128,0,0]
                elif self.world[i,j] == 'P':
                    rgb[i,j] = [0,0,200]
                elif self.world[i,j] == 'X':
                    rgb[i,j] = [206,24,206]
                elif self.world[i,j] == 'C':
                    rgb[i,j] = [0,255,0]
                    
        rgb = rgb.transpose(2,0,1)
        return rgb
    
    def _get_reward(self):
        state = self._check_state()
        if state == 1: #all the boxes are placed
            return 10
        elif state == 2: #a box was placed on a target
            return 1
        elif state == 3: #a box was removed from the target
            return -1
        elif state == -1: #undefined state
            raise RuntimeError("Undefined state")
        elif state == 4: #player changes its position without any consequence
            return -0.1
