"""MCP tools served by this server.

These are simple utility tools consumed by agent apps.
"""
from datetime import datetime, timezone
from pydantic import BaseModel, Field


def load_tools(mcp_server):
    """Register all tools on the FastMCP server instance."""

    @mcp_server.tool
    def get_current_time() -> str:
        """Get the current date and time in UTC. Use this when the user asks about the current time or date."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    @mcp_server.tool
    def calculator(expression: str) -> str:
        """Evaluate a math expression and return the result.

        Args:
            expression: A mathematical expression like '2 + 3 * 4' or '(10 / 2) ** 3'.
                        Only numeric operators (+, -, *, /, **, ()) are allowed.
        """
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expression):
            return "Error: Only numeric expressions with +, -, *, /, **, () are allowed."
        try:
            result = eval(expression)
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    class PersonProfile(BaseModel):
        role: str = Field(description="Job title or role")
        department: str = Field(description="Department")
        expertise: list[str] = Field(description="Areas of expertise")
        location: str = Field(description="Office location")

    _directory = {
        "Alice": PersonProfile(
            role="Staff Data Engineer",
            department="Platform Engineering",
            expertise=["Apache Spark", "Delta Lake", "Data Pipelines", "Python"],
            location="San Francisco",
        ),
        "Bob": PersonProfile(
            role="Senior ML Engineer",
            department="AI/ML",
            expertise=["MLflow", "Model Serving", "PyTorch", "LLMs"],
            location="New York",
        ),
        "Carol": PersonProfile(
            role="Engineering Manager",
            department="Data Platform",
            expertise=["System Design", "Team Leadership", "Lakehouse Architecture"],
            location="Seattle",
        ),
    }

    @mcp_server.tool
    def lookup_employee(name: str) -> dict:
        """Look up an employee's profile from the company directory.

        Args:
            name: The employee's first name (e.g. 'Alice', 'Bob', 'Carol').
        """
        profile = _directory.get(name)
        if profile is None:
            available = ", ".join(_directory.keys())
            return {"error": f"Unknown employee: {name}. Available: {available}"}
        return profile.model_dump()
