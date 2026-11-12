import os
import pickle
import random
import sys
import neat
import pygame

# Window and simulation constants
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 600
SIM_WIDTH = 800
SIM_HEIGHT = 600
UI_PANEL_WIDTH = 400
FPS = 60

# Colors
WHITE = (255, 255, 255)
CREATURE_COLOR = (52, 152, 219)   # Blue for creatures so green Food stands out
FOOD_GREEN = (46, 204, 113)       # Green square for food
PURPLE = (155, 89, 182)           # Purple square for poison
DARK_GRAY = (40, 40, 40)
YELLOW = (255, 215, 0)
LIGHT_GRAY = (220, 220, 220)
NODE_COLOR = (235, 235, 235)
NODE_BORDER = (20, 20, 20)
WEIGHT_POS = (46, 204, 113)
WEIGHT_NEG = (231, 76, 60)

# Initialize Pygame and screen
pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("2D Artificial Life Simulation")
font = pygame.font.SysFont(None, 18)
title_font = pygame.font.SysFont(None, 24)

# Global tracker for champion genome across all generations
best_genome_overall = None


class Creature:
    """Represents a creature entity in the 2D simulation."""

    def __init__(self, center_x, center_y, size=20, speed=5, color=CREATURE_COLOR):
        self.rect = pygame.Rect(0, 0, size, size)
        self.rect.center = (center_x, center_y)
        self.speed = speed
        self.color = color
        self.energy = 200
        self.alive = True

    @property
    def x(self):
        return self.rect.x

    @x.setter
    def x(self, val):
        self.rect.x = val

    @property
    def y(self):
        return self.rect.y

    @y.setter
    def y(self, val):
        self.rect.y = val

    def move(self, direction):
        """Move the creature based on direction index (0: Up, 1: Down, 2: Left, 3: Right)."""
        if direction == 0:  # Up
            self.rect.y -= self.speed
        elif direction == 1:  # Down
            self.rect.y += self.speed
        elif direction == 2:  # Left
            self.rect.x -= self.speed
        elif direction == 3:  # Right
            self.rect.x += self.speed

    def draw(self, surface):
        """Render the creature on the provided surface."""
        pygame.draw.rect(surface, self.color, self.rect)


class Food:
    """Represents a food item (Green square) that creatures consume for energy/fitness."""

    def __init__(self, size=10, color=FOOD_GREEN):
        self.size = size
        self.color = color
        self.rect = pygame.Rect(0, 0, size, size)
        self.respawn()

    def respawn(self):
        """Instantly reposition the food within the 800x600 simulation area."""
        self.rect.x = random.randint(0, SIM_WIDTH - self.size)
        self.rect.y = random.randint(0, SIM_HEIGHT - self.size)

    def draw(self, surface):
        """Render the food item on the provided surface."""
        pygame.draw.rect(surface, self.color, self.rect)


class Poison:
    """Represents a poison hazard (Purple square) that kills creatures upon contact."""

    def __init__(self, size=10, color=PURPLE):
        self.size = size
        self.color = color
        self.rect = pygame.Rect(0, 0, size, size)
        self.respawn()

    def respawn(self):
        """Instantly reposition the poison within the 800x600 simulation area."""
        self.rect.x = random.randint(0, SIM_WIDTH - self.size)
        self.rect.y = random.randint(0, SIM_HEIGHT - self.size)

    def draw(self, surface):
        """Render the poison on the provided surface."""
        pygame.draw.rect(surface, self.color, self.rect)


def draw_network(surface, genome, start_x, start_y):
    """Renders the neural network architecture of a genome on the UI panel."""
    node_positions = {}

    # Hardcoded positions for 4 input nodes on the left side of UI panel
    # -1: Food dX, -2: Food dY, -3: Poison dX, -4: Poison dY
    node_positions[-1] = (start_x + 70, start_y + 130)
    node_positions[-2] = (start_x + 70, start_y + 230)
    node_positions[-3] = (start_x + 70, start_y + 330)
    node_positions[-4] = (start_x + 70, start_y + 430)

    # Hardcoded positions for 4 output nodes on the right side of UI panel
    # 0: Up, 1: Down, 2: Left, 3: Right
    node_positions[0] = (start_x + 330, start_y + 130)
    node_positions[1] = (start_x + 330, start_y + 230)
    node_positions[2] = (start_x + 330, start_y + 330)
    node_positions[3] = (start_x + 330, start_y + 430)

    # Dynamically calculate positions for any hidden nodes in the middle
    hidden_nodes = [k for k in genome.nodes.keys() if k not in (0, 1, 2, 3)]
    if hidden_nodes:
        step_y = 360 / (len(hidden_nodes) + 1)
        for idx, h_id in enumerate(hidden_nodes):
            node_positions[h_id] = (start_x + 200, int(start_y + 120 + (idx + 1) * step_y))

    # Panel Title
    title_surf = title_font.render("ALPHA NEURAL NETWORK", True, LIGHT_GRAY)
    surface.blit(title_surf, (start_x + 85, start_y + 25))

    # Draw connection lines
    for cg in genome.connections.values():
        if cg.enabled:
            in_node, out_node = cg.key
            if in_node in node_positions and out_node in node_positions:
                start_pos = node_positions[in_node]
                end_pos = node_positions[out_node]

                # Green if weight > 0, Red if weight < 0
                color = WEIGHT_POS if cg.weight > 0 else WEIGHT_NEG

                # Thickness proportional to absolute value of the weight
                thickness = max(1, min(int(abs(cg.weight) * 2.5), 8))

                pygame.draw.line(surface, color, start_pos, end_pos, thickness)

    # Draw node circles and text labels
    labels = {
        -1: "F_dx",
        -2: "F_dy",
        -3: "P_dx",
        -4: "P_dy",
        0: "Up",
        1: "Down",
        2: "Left",
        3: "Right",
    }

    for node_id, pos in node_positions.items():
        # Node circle and outline
        pygame.draw.circle(surface, NODE_COLOR, pos, 12)
        pygame.draw.circle(surface, NODE_BORDER, pos, 12, 2)

        # Labels
        label_text = labels.get(node_id, f"H{node_id}")
        txt_surf = font.render(label_text, True, LIGHT_GRAY)
        if node_id in (-1, -2, -3, -4):
            surface.blit(txt_surf, (pos[0] - txt_surf.get_width() - 16, pos[1] - txt_surf.get_height() // 2))
        elif node_id in (0, 1, 2, 3):
            surface.blit(txt_surf, (pos[0] + 16, pos[1] - txt_surf.get_height() // 2))
        else:
            surface.blit(txt_surf, (pos[0] - txt_surf.get_width() // 2, pos[1] - 24))


def eval_genomes(genomes, config):
    """Evaluates the fitness of each genome in the population over a simulation generation."""
    nets = []
    ge = []
    creatures = []

    # Initialize neural network, genome fitness, and creature instance for each genome
    for genome_id, genome in genomes:
        net = neat.nn.FeedForwardNetwork.create(genome, config)
        nets.append(net)
        genome.fitness = 0
        ge.append(genome)
        creatures.append(Creature(center_x=SIM_WIDTH // 2, center_y=SIM_HEIGHT // 2))

    food = Food()
    poison = Poison()
    clock = pygame.time.Clock()
    running = True

    while running and len(creatures) > 0:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        # Update each creature via its neural network (iterate in reverse for safe popping)
        for i in range(len(creatures) - 1, -1, -1):
            creature = creatures[i]

            # Decrease energy by 1 every single frame
            creature.energy -= 1

            # If energy is depleted naturally, mark as dead and remove
            if creature.energy <= 0:
                creature.alive = False
                creatures.pop(i)
                nets.pop(i)
                ge.pop(i)
                continue

            # 1. Calculate X and Y distances to Food and Poison
            food_dx = food.rect.centerx - creature.rect.centerx
            food_dy = food.rect.centery - creature.rect.centery
            poison_dx = poison.rect.centerx - creature.rect.centerx
            poison_dy = poison.rect.centery - creature.rect.centery

            # 2. Pass all 4 sensory distances to neural network
            output = nets[i].activate((food_dx, food_dy, poison_dx, poison_dy))

            # 3. Highest output value maps to direction (0: Up, 1: Down, 2: Left, 3: Right)
            decision = output.index(max(output))
            creature.move(decision)

            # 4. Out-of-bounds wall collision: lethal boundary (treat wall like poison)
            if (
                creature.rect.left < 0
                or creature.rect.right > SIM_WIDTH
                or creature.rect.top < 0
                or creature.rect.bottom > SIM_HEIGHT
            ):
                ge[i].fitness -= 10
                creature.alive = False
                creatures.pop(i)
                nets.pop(i)
                ge.pop(i)
                continue

            # 5. Reward +0.1 fitness per frame alive
            ge[i].fitness += 0.1

            # 5. Food collision: +20 fitness and respawn food
            if creature.rect.colliderect(food.rect):
                ge[i].fitness += 20
                food.respawn()

            # 6. Poison collision: instant kill, fitness penalty, and immediate array removal
            if creature.rect.colliderect(poison.rect):
                ge[i].fitness -= 20
                creature.alive = False
                poison.respawn()
                creatures.pop(i)
                nets.pop(i)
                ge.pop(i)
                continue

        # When all creatures have died, break loop to advance to next generation
        if len(creatures) == 0:
            break

        # Rendering
        screen.fill(WHITE)

        # Simulation field (left 800x600)
        food.draw(screen)
        poison.draw(screen)
        for creature in creatures:
            creature.draw(screen)

        alpha_genome = None
        # Identify alpha creature with the highest current fitness score
        if ge:
            max_idx = max(range(len(ge)), key=lambda idx: ge[idx].fitness)
            alpha_genome = ge[max_idx]
            alpha_net = nets[max_idx]
            alpha_creature = creatures[max_idx]

            global best_genome_overall
            if best_genome_overall is None or alpha_genome.fitness > best_genome_overall.fitness:
                best_genome_overall = alpha_genome

            # Draw yellow highlight ring around alpha_creature
            pygame.draw.circle(screen, YELLOW, alpha_creature.rect.center, radius=18, width=2)

        # UI panel (right 400x600)
        pygame.draw.rect(screen, DARK_GRAY, (SIM_WIDTH, 0, UI_PANEL_WIDTH, WINDOW_HEIGHT))

        # Render neural network of alpha creature on the UI panel
        if alpha_genome is not None:
            draw_network(screen, alpha_genome, start_x=SIM_WIDTH, start_y=0)

        pygame.display.flip()
        clock.tick(FPS)


def run(config_path):
    """Loads configuration and runs the NEAT evolutionary simulation."""
    # Load configuration
    config = neat.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        config_path,
    )

    # Initialize the Population
    p = neat.Population(config)

    # Add StdOutReporter to display statistics in the terminal
    p.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    p.add_reporter(stats)

    # Automatically save simulation checkpoints every 10 generations
    p.add_reporter(neat.Checkpointer(10))

    # Run simulation for up to 500 generations
    winner = None
    try:
        winner = p.run(eval_genomes, 500)
    except KeyboardInterrupt:
        print("\n[Ctrl+C detected] Simulation manually interrupted by user.")
        winner = p.best_genome or best_genome_overall

    # Save the ultimate winning genome permanently to best_dna.pkl
    target_genome = winner or p.best_genome or best_genome_overall
    if target_genome is not None:
        print(f"\nBest genome:\n{target_genome}")
        save_path = os.path.join(os.path.dirname(os.path.abspath(config_path)), "best_dna.pkl")
        with open(save_path, "wb") as file:
            pickle.dump(target_genome, file)
        print(f"Saved best genome permanently to {save_path}")
    else:
        print("Simulation stopped before any genome could be evaluated.")


if __name__ == "__main__":
    local_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(local_dir, "config.txt")
    run(config_path)
