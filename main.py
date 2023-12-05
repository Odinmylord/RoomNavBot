import json
import pyrogram
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import configparser

cardinal_dict = {
    "N": 0,
    "E": 1,
    "S": 2,
    "W": 3
}
degrees_to_human = {
    0: "front",
    90: "right",
    180: "back",
    270: "left"
}

floors = ["povo1_1", "povo1_0"]

keyboard_floors = InlineKeyboardMarkup([
    [InlineKeyboardButton("Povo 1, ground floor (A101-A110)", callback_data="povo1_0")],
    [InlineKeyboardButton("Povo 1, first floor (A201-A224)", callback_data="povo1_1")]
])


class Graph:
    def __init__(self, floor):
        self.nodes = []
        with open(floor, "r") as f:
            data = json.load(f)
        for name in data:
            orientation = data[name]["orientation"]
            if not orientation:
                orientation = None
            self.add_node(Node(name, orientation))
        for name in data:
            for edge in data[name]["edges"]:
                self.add_edge(name, Edge(self.get_by_name(edge[0]), edge[1], edge[2]))
    
    def add_node(self, node):
        self.nodes.append(node)
    
    def add_edge(self, source, edge):
        for node in self.nodes:
            if node.name == source:
                node.edges.append(edge)
                return
        raise Exception("Node not found")
    
    def get_by_name(self, name):
        for node in self.nodes:
            if node.name == name:
                return node
        return None
    
    def print(self):
        for node in self.nodes:
            print(node.name, node.orientation, node.distance)
            for edge in node.edges:
                print("\t", edge.destination.name, edge.orientation, edge.distance)
    
    def dijkstra(self, from_node, to_node):
        unvisited = self.nodes.copy()
        for node in unvisited:
            node.distance = float("inf")
            node.previous = None
        from_node.distance = 0
        while len(unvisited) > 0:
            current = min(unvisited, key=lambda node: node.distance)
            unvisited.remove(current)
            for edge in current.edges:
                if edge.destination in unvisited:
                    if current.distance + edge.distance < edge.destination.distance:
                        edge.destination.distance = current.distance + edge.distance
                        edge.destination.previous = current
        path = []
        current = to_node
        while current is not None:
            path.append(current)
            current = current.previous
        path.reverse()
        return path

    def get_room_from_corridor(self, corridor):
        node = self.get_by_name(corridor)
        if node is None:
            return None
        for edge in node.edges:
            if not edge.destination.name.startswith("Cross") and not edge.destination.name.startswith("Corridor"):
                return edge.destination.name
        return None
class Node:
    def __init__(self, name, orientation):
        self.name = name
        self.orientation = orientation
        self.edges = []

    def get_direction_to(self, destination):
        for edge in self.edges:
            if edge.destination == destination:
                return edge.orientation
        return None

class Edge:
    def __init__(self, destination: Node, distance, orientation):
        self.destination = destination
        self.distance = int(distance)
        self.orientation = orientation

def direction_converter(direction, new_direction):
    if new_direction is None:
        new_direction = direction
    return degrees_to_human[((cardinal_dict[new_direction] - cardinal_dict[direction]) % 4) * 90]



def pathfinder(graph: Graph, room1, room2):
    path = graph.dijkstra(graph.get_by_name(room1), graph.get_by_name(room2))
    steps = []
    path_dir = []
    # add direction to the nodes
    for i in range(len(path)-1):
        path_dir.append((path[i+1], path[i].get_direction_to(path[i+1])))
    currently_facing = graph.get_by_name(room1).orientation
    for node, direction in path_dir:
        steps.append((node.name, direction_converter(currently_facing, direction)))
        if direction:
            currently_facing = direction
    output_string = "Exit the room and watch the door. "
    counter = 0
    for room, direction in steps:
        direction = "Walk straight " if direction == "front" else "Turn to " + direction + ", "
        output_string += "\n"
        if room.startswith("Cross") and counter == 0:
            output_string += "Walk to the nearest corner, while watching in the direction of the door of the room you were in. " + direction[:-2]
        elif room.startswith("Cross"):
            additional_string = "and walk up " if not direction.startswith("Walk") else ""
            output_string += direction + additional_string + "up to the corner."
        elif room.startswith("Corridor") and counter != len(steps)-2:
            near_room = graph.get_room_from_corridor(room)
            if counter:
                additional_string = "and go past " + near_room + "."
            else:
                additional_string = "."
                direction = direction[:-2]
            output_string += direction + additional_string
        elif room.startswith("Corridor") and counter == len(steps)-2:
            additional_string = "and walk up " if not direction.startswith("Walk") else ""
            output_string += direction + additional_string + "to the door of the next room."
        elif counter == 0:
            output_string += direction[:-2]+"."
        elif room == "Entrance" and counter == len(steps)-1:
            output_string += direction + "and and after walking a few steps you will find the entrance in front of you."
        elif room == "Entrance":
            output_string += direction + "and go past the entrance."
        else:
            output_string += direction + "and you will find " + room + " in front of you."
        
        counter += 1
    print(output_string)

if __name__ == "__main__":            
    # init pyrogram using data from config.ini
    configparser = configparser.ConfigParser()
    configparser.read("config.ini")
    pyrogram_config = configparser["pyrogram"]
    pyrogram_config["api_id"] = int(pyrogram_config["api_id"])
    app = pyrogram.Client(
        "navbot",
        api_id=pyrogram_config["api_id"],
        api_hash=pyrogram_config["api_hash"],
        bot_token=pyrogram_config["bot_token"]
    )
    app = pyrogram.Client()
    app.run()

@app.on_message(pyrogram.filters.command("start"))
def start(client, message):
    message.reply_text("Use the /nav command to start navigating")

# add event handler for start
@app.on_message(pyrogram.filters.command("nav"))
def start(client, message):
    message.reply_text("Choose a floor", reply_markup=keyboard_floors)

# check if callback is in floors with a filter
floors_filter = pyrogram.filters.create(
    lambda _, __, query: query.data in floors
)
@app.on_callback_query(floors_filter)
def floor_callback(client, callback_query):
    # get floor from callback data
    floor = callback_query.data
    # create graph
    graph = Graph(floor=floor+".json")
    # send message
    callback_query.message.reply_text("Choose a room")
    # create keyboard
    keyboard = InlineKeyboardMarkup()
    # add rooms to keyboard
    for node in graph.nodes:
        keyboard.row(InlineKeyboardButton(node.name, callback_data=node.name))
    # send keyboard
    callback_query.message.reply_text("Choose a room", reply_markup=keyboard)
