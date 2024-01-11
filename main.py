import json
import pyrogram
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
import configparser
import os
from PIL import Image, ImageDraw
import io

cardinal_dict = {"N": 0, "E": 1, "S": 2, "W": 3}
degrees_to_human = {0: "front", 90: "right", 180: "back", 270: "left"}

floors = ["povo1_1", "povo1_0"]

keyboard_floors = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "Povo 1, ground floor (A101-A110)", callback_data="povo1_0"
            )
        ],
        [
            InlineKeyboardButton(
                "Povo 1, first floor (A201-A224)", callback_data="povo1_1"
            )
        ],
    ]
)


class Graph:
    def __init__(self, floor):
        self.nodes = []
        with open(floor, "r") as f:
            data = json.load(f)
        for name in data:
            orientation = data[name]["orientation"]
            coords = data[name].get("coords")
            if not orientation:
                orientation = None
            self.add_node(Node(name, orientation, coords))
        for name in data:
            for edge in data[name]["edges"]:
                self.add_edge(name, Edge(self.get_by_name(edge[0]), edge[1], edge[2]))
        self.floor = floor

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
            if not edge.destination.name.startswith(
                "Cross"
            ) and not edge.destination.name.startswith("Corridor"):
                return edge.destination.name
        return None


class Node:
    def __init__(self, name, orientation, coords):
        self.name = name
        self.orientation = orientation
        self.coords = coords
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
    return degrees_to_human[
        ((cardinal_dict[new_direction] - cardinal_dict[direction]) % 4) * 90
    ]


def prepare_image(graph, path):
    file = "images/" + graph.floor.replace("json", "png")
    if os.path.isfile(file):
        with open(file, "rb") as f:
            img = Image.open(f)
            draw = ImageDraw.Draw(img)
        # Draw a circle in the first point
        draw.ellipse(
            (
                path[0].coords[0] - 5,
                path[0].coords[1] - 5,
                path[0].coords[0] + 5,
                path[0].coords[1] + 5,
            ),
            fill="red",
        )
        for i in range(len(path) - 1):
            draw.line(
                path[i].coords + path[i + 1].coords,
                fill="red",
                width=5,
            )
        # draw a triangle in the last point
        draw.polygon(
            (
                path[-1].coords[0],
                path[-1].coords[1] - 5,
                path[-1].coords[0] - 5,
                path[-1].coords[1] + 5,
                path[-1].coords[0] + 5,
                path[-1].coords[1] + 5,
            ),
            fill="red",
        )
        image = io.BytesIO()
        img.save(image, format="PNG")
        image.name = "image.png"
        return image


def pathfinder(graph: Graph, room1, room2):
    path = graph.dijkstra(graph.get_by_name(room1), graph.get_by_name(room2))
    image = prepare_image(graph, path)
    steps = []
    path_dir = []
    # add direction to the nodes
    for i in range(len(path) - 1):
        path_dir.append((path[i + 1], path[i].get_direction_to(path[i + 1])))
    currently_facing = graph.get_by_name(room1).orientation
    for node, direction in path_dir:
        steps.append((node.name, direction_converter(currently_facing, direction)))
        if direction:
            currently_facing = direction
    output_string = "Exit the room and watch the door. "
    counter = 0
    for room, direction in steps:
        direction = (
            "Walk straight " if direction == "front" else "Turn to " + direction + ", "
        )
        output_string += "\n"
        if room.startswith("Cross") and counter == 0:
            output_string += (
                "Walk to the nearest corner, while watching in the direction of the door of the room you were in. "
                + direction[:-2]
            )
        elif room.startswith("Cross"):
            additional_string = (
                "and walk up " if not direction.startswith("Walk") else ""
            )
            output_string += direction + additional_string + "up to the corner."
        elif room.startswith("Corridor") and counter != len(steps) - 2:
            near_room = graph.get_room_from_corridor(room)
            if counter:
                additional_string = "and go past " + near_room + "."
            else:
                additional_string = "."
                direction = direction[:-2]
            output_string += direction + additional_string
        elif room.startswith("Corridor") and counter == len(steps) - 2:
            additional_string = (
                "and walk up " if not direction.startswith("Walk") else ""
            )
            output_string += (
                direction + additional_string + "to the door of the next room."
            )
        elif counter == 0:
            output_string += direction[:-2] + "."
        elif room == "Entrance" and counter == len(steps) - 1:
            output_string += (
                direction
                + "and and after walking a few steps you will find the entrance in front of you."
            )
        elif room == "Entrance":
            output_string += direction + "and go past the entrance."
        else:
            output_string += (
                direction + "and you will find " + room + " in front of you."
            )

        counter += 1
    return output_string, image


parser = configparser.ConfigParser()
parser.read("config.ini")
pyrogram_config = parser["pyrogram"]
app = pyrogram.Client(
    "navbot",
    api_id=pyrogram_config["api_id"],
    api_hash=pyrogram_config["api_hash"],
    bot_token=pyrogram_config["bot_token"],
)

graphs = {}
for floor in floors:
    graphs[floor] = Graph(floor=floor + ".json")


@app.on_message(pyrogram.filters.command("start") & pyrogram.filters.private)
def start(_, message):
    print(message.text)
    message.reply_text("Use the /nav command to start navigating")
    return True


@app.on_message(pyrogram.filters.command("nav") & pyrogram.filters.private)
def nav(_, message):
    message.reply_text("Choose a floor", reply_markup=keyboard_floors)
    return True


# check if callback is in floors with a filter
floors_filter = pyrogram.filters.create(lambda _, __, query: query.data in floors)


@app.on_callback_query(floors_filter)
def floor_callback(client, callback_query):
    # get floor from callback data
    floor = callback_query.data
    # create graph
    graph = Graph(floor=floor + ".json")
    # create keyboard
    keyboard = []
    # add rooms to keyboard
    for node in graph.nodes:
        if node.name.startswith("Corridor") or node.name.startswith("Cross"):
            continue
        keyboard.append(
            [InlineKeyboardButton(node.name, callback_data=floor + "$" + node.name)]
        )
    keyboard = InlineKeyboardMarkup(keyboard)
    # send keyboard
    callback_query.edit_message_text("Choose a room", reply_markup=keyboard)


def room_filter(_, __, query):
    if query.data.count("$") != 1:
        return False
    floor, room = query.data.split("$")
    node_names = [node.name for node in graphs[floor].nodes]
    return floor in floors and room in node_names


first_room_filter = pyrogram.filters.create(room_filter)


@app.on_callback_query(first_room_filter)
def first_room_callback(client, callback_query: pyrogram.types.CallbackQuery):
    floor, room = callback_query.data.split("$")
    print(floor, room)
    keyboard = []
    for node in graphs[floor].nodes:
        if (
            node.name.startswith("Corridor")
            or node.name.startswith("Cross")
            or node.name == room
        ):
            continue
        keyboard.append(
            [
                InlineKeyboardButton(
                    node.name, callback_data=floor + "$" + room + "$" + node.name
                )
            ]
        )
    keyboard = InlineKeyboardMarkup(keyboard)
    callback_query.edit_message_text(
        f"Starting point: {room}.\nChoose destination room", reply_markup=keyboard
    )
    return True


def double_room_filter(_, __, query):
    if query.data.count("$") != 2:
        return False
    floor, room1, room2 = query.data.split("$")
    node_names = [node.name for node in graphs[floor].nodes]
    return floor in floors and room1 in node_names and room2 in node_names


second_room_filter = pyrogram.filters.create(double_room_filter)


@app.on_callback_query(second_room_filter)
def second_room_callback(client, callback_query):
    floor, room1, room2 = callback_query.data.split("$")
    path, image = pathfinder(graphs[floor], room1, room2)
    callback_query.message.reply_photo(image, caption=path)
    return True


@app.on_callback_query()
def print_query(_, query):
    print(query.data)


@app.on_message(pyrogram.filters.command("start") & pyrogram.filters.private)
def start(_, message):
    message.reply_text("This bot will help you find rooms inside Povo.\nUse the /nav command to start navigating")
    return True


app.run()
