from game_consts import *
from tree_search import SearchProblem, SearchTree
from pathways import Pathways
from corridor import Corridor
from ghost_info import Ghost_Info
from pacman_info import Pacman_Info
import logging

# logs are written to file advisor.log after the client is closed
# possible messages: debug, info, warning, error, critical 
# how to use: logger.typeOfMessage('message')
logger = logging.getLogger('advisor')
logger_format = '[%(lineno)s - %(funcName)20s() - %(levelname)s]\n %(message)s\n'
#logger_format = '%(levelname)s:\t%(message)' # simpler format

# currently writing over the logger file, change filemode to a to append
logging.basicConfig(format=logger_format, filename='advisor.log', filemode='w', level=logging.DEBUG)

# logger
# logs are written to file strategy_advisor.log after the client is closed
# possible messages: debug, info, warning, error, critical 
# how to use: logger.typeOfMessage('message')
logger = setup_logger('strategy_advisor', 'strategy_advisor.log')

class Strategy_Advisor():
    """Analyses corridors safety (if contains ghost or not) and crossroads
    semaphores. Advises on a strategy for the given conditions.

    Args:
    map_: instance of Map for the current level
    state: the game state given by the server

    Attr:
    ghosts: A set of quadruples with (ghost_position, zombie, timeout, distance_to_pacman)
    """

    def __init__(self, map_, state):
        self.map_ = map_
        self.state = state
        self.unsafe_corridors = self.set_corridors_safety()
        self.pacman_info = Pacman_Info(state['pacman'])
        self.calculate_pacman_corridor()
        self.ghosts_info = self.calculate_ghosts_info()
        self.calculate_semaphores()
    

    def advise(self):
        """Given the safety of corridors and crossroads, advises a MODE of play

        Returns: the advised MODE of play
        """
        
        logger.debug("########################################################")
        logger.debug("ADVISE()")
        logger.debug("########################################################")

        ### Advise on a Mode of play given the previous analysis 

        # There is at least one side of pacman with no ghosts at a safe distance
        # Eating Mode is advised
        ghosts_dists_to_pacman = [ghost.dist_to_pacman for ghost in self.ghosts_info]
        logger.debug("GHOSTS_DISTS_TO_PACMAN:\n" + str(ghosts_dists_to_pacman))
        any_safe_dist = any([ dist >= SAFE_DIST_TO_GHOST for dist in ghosts_dists_to_pacman] )
        logger.debug("ANY SAFE DIST:\n" + str(any_safe_dist))
        if any_safe_dist:
            return MODE.EATING

        # All directions from Pac-Man have ghosts closer than the safe distance
        # Semaphores must be evaluated to choose better Mode
        semaphores = [self.pacman_info.semaphore0, self.pacman_info.semaphore0]
        if any([color == SEMAPHORE.GREEN for color in semaphores]):
            return MODE.EATING
        elif any([color == SEMAPHORE.YELLOW for color in semaphores]):
            if len(self.state['boosts']) > 0:
                return MODE.COUNTER
            return MODE.FLIGHT
        else:
            return MODE.EATING

        

    #* COMPLETE - NOT TESTED
    def set_corridors_safety(self):
        """Sets the corridors safety flag according to the existence of ghosts

        Args:
        ghots: a list with the position of all non zombie ghosts

        Returns:
        A list of tuples with the unsafe corridors and the position of the ghost
        in that corridor. If more than one ghost is in a given corridors, the
        corridor is returned multiple times tupled with each ghost 
        """

        logger.debug("########################################################")
        logger.debug("SET_CORRIDORS_SAFETY()")
        logger.debug("########################################################")

        unsafe_corridors = []
        for ghost in [ghost for ghost in self.state['ghosts'] if ghost[1] == False]: # non zombie ghosts
            for [cA, cB] in self.map_.corr_adjacencies:
                if ghost[0] in cA.coordinates:     # pode dar erro: pesquisar [x,y] em (x,y)
                    cA.safe = CORRIDOR_SAFETY.UNSAFE
                    unsafe_corridors += [cA]
                elif ghost[0] in cB.coordinates:
                    cB.safe = CORRIDOR_SAFETY.UNSAFE
                    unsafe_corridors += [cB]
                else:
                    cA.safe = CORRIDOR_SAFETY.SAFE
                    cA.safe = CORRIDOR_SAFETY.SAFE
        logger.debug("UNSAFE_CORRIDORS:\n" + str(unsafe_corridors))
        return unsafe_corridors
            


    def calculate_ghosts_info(self):

        non_zombie_ghosts = [ghost for ghost in self.state['ghosts'] if ghost[1] == False]
        domain = Pathways(self.map_.corr_adjacencies, non_zombie_ghosts)
        pacman = self.pacman_info.position
        pac_corridor = self.pacman_info.corridor
        ghosts_info = []

        for (ghost,zombie,timeout) in non_zombie_ghosts: # non zombie ghosts

            # get the corridor the ghost is in to give as argument in search
            ghost_corr = None
            if ghost not in self.map_.ghosts_den:
                for corr in self.unsafe_corridors:
                    if ghost in corr.coordinates:
                        ghost_corr = corr
                        break

            # calculate trajectory of every ghost towards Pac-Man
            if not ghost_corr == None: # if ghost is not in ghosts_den
                my_prob = SearchProblem(domain, ghost_corr, ghost, self.pacman_info.corridor, pacman)
                my_tree = SearchTree(my_prob, "a*")
                #TODO if result is None, program breaks
                _, cost, path = my_tree.search()
            else:
                continue

            # the crossroad that the ghost will use to get to Pac-Man
            crossroad = path[-2].ends[0] if path[-2].ends[0] != pacman else path[-2].ends[1]

            # calculate distance of every ghost to Pac-Man crossroads
            ghost_dist = cost - pac_corridor.dist_end(pacman, crossroad)

            # update sel.ghosts with new attribute of distance_to_pacman
            ghosts_info += [Ghost_Info((ghost, zombie, timeout), ghost_corr, cost, crossroad, ghost_dist)]

        return ghosts_info



    def calculate_pacman_corridor(self):

        # Pac-Man position and his corridor (or list of corridors if Pac-Man is in crossroad)
        pacman = (self.state['pacman'])
        pac_corridor = [ corr for corr in self.map_.corridors if pacman in corr.coordinates ]
        logger.debug("PACMAN POSITION:\n" + str(pacman))
        logger.debug("PACMAN CORRIDORS:\n" + str(pac_corridor))

        # Pac-Man might be at a crossroad. Choose unsafe corridor if available.
        for corr in pac_corridor:
            if corr.safe == CORRIDOR_SAFETY.UNSAFE:
                pac_corridor = [corr]
                break
        self.pacman_info.update_corridor(pac_corridor[0])
        logger.debug("PACMAN CHOSEN CORRIDOR:\n" + str(pac_corridor))



    def calculate_semaphores(self):
        """Attributes a SEMAPHORE color for each crossroad in Pac-Man's corridor
        by comparingthe distance of Pac-Man and the closest ghost to that
        crossroad

        Args:
        unsafe_corridors: list of corridors that have a ghost
        pac_corridor: the corridor Pac-Man is in
        pacman: the coordinates of Pac-Man position

        Returns:
        A dictionary with key = crossroad and value of a tuple with the distance
        of the ghost to Pac-Man and the distance of the ghost to the crossroad
        """

        logger.debug("########################################################")
        logger.debug("CALCULATE_SEMAPHORES()")
        logger.debug("########################################################")

        # get ends of Pac-Man corridor
        pacman = self.pacman_info

        # verify crossroads semaphores
        semaphores = {} # {crossroad : [Ghost_Info]}
        for ghost in self.ghosts_info:
            #print("\n\n")
            #print(semaphores)
            #print(ghost.crossroad_to_pacman)
            
            #! FIXED BUG. LISTS CAN'T BE KEYS IN DICTIONARIES
            key = ghost.crossroad_to_pacman[0], ghost.crossroad_to_pacman[1]
            if key not in semaphores.keys():
                semaphores[key] = [ghost]
            else: # gdt(p/c) -> ghost.dist_to_(pacman/crossroad)
                semaphores[key] += [ghost]
                
        # select most dangerous ghost distancies
        if len(semaphores) > 0: # there are no ghosts, or all are zombie
            pacman.semaphore0 = SEMAPHORE.GREEN
            pacman.semaphore1 = SEMAPHORE.GREEN
        else: # TODO solve temporary solution for when ghosts are in the den, in method above
            for cross in semaphores:
                ghost = min(semaphores[cross], key=lambda x : x.dist_to_crossroad)

        # compare distance of Pac-Man and ghosts to crossroads and
        # convert semaphores to colors
        for cross in semaphores:

            if cross == pacman.crossroad0:
                dist_to_end = pacman.dist_to_crossroad0
                pacman.dist_to_ghost_at_crossroad0 = semaphores[cross].dist_to_crossroad
                pacman.crossroad0_is_safe = semaphores[cross].dist_to_pacman >= SAFE_DIST_TO_GHOST

                if semaphores[cross].dist_to_crossroad > dist_to_end + 1:
                    pacman.semaphore0 = SEMAPHORE.GREEN
                elif semaphores[cross].dist_to_crossroad == dist_to_end + 1:
                    pacman.semaphore0 = SEMAPHORE.YELLOW
                else:
                    pacman.semaphore0 = SEMAPHORE.RED

            else:
                dist_to_end = pacman.dist_to_crossroad1
                print("----" + str(cross))
                print(semaphores[cross])
                print("--------")

                #! several ghosts for a given crossroad
                #! please verify. the idea is, for each ghost i verify the way it was being done
                #! the worst color wins 
                pacman.semaphore1 = SEMAPHORE.GREEN
                for ghost in semaphores[cross]:
                    pacman.dist_to_ghost_at_crossroad1 = ghost.dist_to_crossroad
                    pacman.crossroad1_is_safe = ghost.dist_to_pacman >= SAFE_DIST_TO_GHOST

                    if ghost.dist_to_crossroad > dist_to_end + 1:
                        if pacman.semaphore1 == SEMAPHORE.GREEN:
                            pacman.semaphore1 = SEMAPHORE.GREEN     #can only be green if it's currently green
                            # could simply be ignored
                    elif ghost.dist_to_crossroad == dist_to_end + 1:
                        if pacman.semaphore1 != SEMAPHORE.RED:
                            pacman.semaphore1 = SEMAPHORE.YELLOW    #can only be yellow if it's currently yellow or green (ie not red)
                    else:
                        pacman.semaphore1 = SEMAPHORE.RED           #can always be red 



    def boosts_analyser(self):
        """

        Args:

        Returns:
        """
        pass
