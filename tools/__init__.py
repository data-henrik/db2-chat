from __future__ import annotations

import json

from tools.db2 import list_tables, run_query, run_query_city_distance, get_nearby_cities
from tools.weather import get_weather
from tools.wikipedia import search_wikipedia

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city to look up.",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_wikipedia",
            "description": "Search Wikipedia and return a summary for a topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The topic to search for.",
                    },
                    "language": {
                        "type": "string",
                        "description": "Wikipedia language.",
                        "enum": ["en", "de"],
                        "default": "en",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_db2_tables",
            "description": "List Db2 tables for a schema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schema": {
                        "type": "string",
                        "description": "Optional Db2 schema name.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_db2",
            "description": "Run a read-only SQL query against Db2.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A SELECT or WITH SQL statement.",
                    }
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_db2_city_distance",
            "description": "Retrieve distance between two cities by querying Db2 via SQL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city1": {
                        "type": "string",
                        "description": "The name of the first city",
                    },
                    "city2": {
                        "type": "string",
                        "description": "The name of the other city to compute the distance",
                    }
                },
                "required": ["city1", "city2"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_nearby_cities",
            "description": (
                "Find the 10 closest cities to a given city. "
                "Use this to answer questions like 'What cities are close to NAME?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The name of the reference city.",
                    }
                },
                "required": ["city"],
            },
        },
    },
]


def call_tool(name: str, arguments: dict) -> str:
    if name == "get_weather":
        result = get_weather(arguments["city"])
    elif name == "search_wikipedia":
        result = search_wikipedia(
            arguments["query"],
            arguments.get("language", "en"),
        )
    elif name == "list_db2_tables":
        result = list_tables(arguments.get("schema"))
    elif name == "query_db2":
        result = run_query(arguments["sql"])
    elif name == "query_db2_city_distance":
        result = run_query_city_distance(arguments["city1"], arguments["city2"])
    elif name == "get_nearby_cities":
        result = get_nearby_cities(arguments["city"])
    else:
        result = {"error": f"Unknown tool: {name}"}

    return json.dumps(result)
