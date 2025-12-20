"""
Quick Capture Agent - CLI Entry Point

This module provides the command-line interface for the multi-agent system.
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table

from quick_capture_agent.orchestrator import HelperAgent
from quick_capture_agent.agents.research import ResearchAgent
from quick_capture_agent.agents.content_collector import ContentCollectorAgent
from quick_capture_agent.knowledge_base import KnowledgeBase, ContentCategory

app = typer.Typer(
    name="qca",
    help="Quick Capture Agent - Your AI-powered helper for research and content collection",
    add_completion=False,
)
console = Console()


def get_helper() -> HelperAgent:
    """Get a configured HelperAgent instance."""
    return HelperAgent()


@app.command()
def run(
    task: str = typer.Argument(..., help="The task to execute"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Specific agent to use"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Execute a task using the helper agent."""

    async def _run():
        helper = get_helper()

        with console.status(f"[bold green]Processing: {task[:50]}..."):
            result = await helper.run(task, context={"agent": agent, "verbose": verbose})

        if result.success:
            console.print(Panel(
                Markdown(str(result.data.get("result", result.data))),
                title="[green]Result",
                border_style="green",
            ))
        else:
            console.print(Panel(
                f"[red]Error: {result.error}",
                title="[red]Failed",
                border_style="red",
            ))

    asyncio.run(_run())


@app.command()
def research(
    topic: str = typer.Argument(..., help="Topic to research"),
    depth: str = typer.Option("standard", "--depth", "-d", help="Research depth: quick, standard, comprehensive"),
):
    """Run a research task."""

    async def _research():
        agent = ResearchAgent()

        with console.status(f"[bold blue]Researching: {topic}..."):
            result = await agent.run(topic, context={"depth": depth})

        if result.success:
            console.print(Panel(
                Markdown(str(result.data.get("findings", result.data))),
                title=f"[blue]Research: {topic[:40]}",
                border_style="blue",
            ))
        else:
            console.print(f"[red]Error: {result.error}")

    asyncio.run(_research())


@app.command()
def collect(
    source: str = typer.Argument(..., help="URL or path to collect"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Category for storage"),
    no_store: bool = typer.Option(False, "--no-store", help="Don't store in knowledge base"),
):
    """Collect and process content from a URL or file."""

    async def _collect():
        agent = ContentCollectorAgent()

        context = {
            "store": not no_store,
        }
        if category:
            context["categories"] = [category]

        with console.status(f"[bold cyan]Collecting: {source[:50]}..."):
            result = await agent.run(source, context=context)

        if result.success:
            console.print(Panel(
                str(result.data),
                title="[cyan]Collected Content",
                border_style="cyan",
            ))
        else:
            console.print(f"[red]Error: {result.error}")

    asyncio.run(_collect())


@app.command()
def kb(
    action: str = typer.Argument(..., help="Action: list, search, stats, get"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Search query"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
    item_id: Optional[str] = typer.Option(None, "--id", help="Item ID for get action"),
):
    """Manage the knowledge base."""
    kb = KnowledgeBase()

    if action == "stats":
        stats = kb.get_stats()
        table = Table(title="Knowledge Base Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Items", str(stats["total_items"]))
        table.add_row("Total Tags", str(stats["total_tags"]))

        for cat, count in stats.get("categories", {}).items():
            table.add_row(f"  {cat}", str(count))

        console.print(table)

    elif action == "list":
        cat = ContentCategory(category) if category else None
        items = kb.search(query=query or "", category=cat)

        table = Table(title="Knowledge Base Items")
        table.add_column("ID", style="dim")
        table.add_column("Title", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Tags", style="yellow")

        for item in items[:20]:
            table.add_row(
                item.id[:12] + "...",
                item.title[:40],
                item.category.value,
                ", ".join(item.tags[:3]),
            )

        console.print(table)

    elif action == "search":
        if not query:
            console.print("[red]Please provide a search query with --query")
            return

        items = kb.search(query=query)
        console.print(f"[green]Found {len(items)} items matching '{query}'")

        for item in items[:10]:
            console.print(Panel(
                f"[bold]{item.title}[/bold]\n\n{item.content[:200]}...",
                title=f"[dim]{item.id}",
                border_style="dim",
            ))

    elif action == "get":
        if not item_id:
            console.print("[red]Please provide an item ID with --id")
            return

        item = kb.get(item_id)
        if item:
            console.print(Panel(
                Markdown(f"# {item.title}\n\n{item.content}"),
                title=f"[cyan]{item.category.value}",
                border_style="cyan",
            ))
        else:
            console.print(f"[red]Item not found: {item_id}")

    else:
        console.print(f"[red]Unknown action: {action}")
        console.print("Available actions: list, search, stats, get")


@app.command()
def agents():
    """List available agents."""
    helper = get_helper()
    agents_info = helper.get_available_agents()

    table = Table(title="Available Agents")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")

    for name, description in agents_info.items():
        table.add_row(name, description)

    console.print(table)


@app.command()
def interactive():
    """Start an interactive session with the helper agent."""
    helper = get_helper()

    console.print(Panel(
        "[bold green]Quick Capture Agent[/bold green]\n\n"
        "Type your requests and press Enter. Type 'quit' to exit.\n"
        "Use '@agent_name' to target a specific agent.",
        title="Interactive Mode",
        border_style="green",
    ))

    async def _interactive():
        while True:
            try:
                user_input = console.input("\n[bold cyan]You:[/bold cyan] ")

                if user_input.lower() in ("quit", "exit", "q"):
                    console.print("[yellow]Goodbye!")
                    break

                if not user_input.strip():
                    continue

                # Check for agent targeting
                agent = None
                if user_input.startswith("@"):
                    parts = user_input.split(" ", 1)
                    if len(parts) == 2:
                        agent = parts[0][1:]  # Remove @
                        user_input = parts[1]

                with console.status("[bold green]Thinking..."):
                    result = await helper.run(user_input, context={"agent": agent})

                if result.success:
                    response = result.data.get("response") or result.data.get("result") or result.data
                    console.print(f"\n[bold green]Assistant:[/bold green] {response}")
                else:
                    console.print(f"\n[bold red]Error:[/bold red] {result.error}")

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Type 'quit' to exit.")
            except Exception as e:
                console.print(f"\n[red]Error: {e}")

    asyncio.run(_interactive())


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
