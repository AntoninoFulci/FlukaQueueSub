from colorama import Fore, Style, init
from tabulate import tabulate

init(autoreset=True)

COLORS = {
    "G":  Fore.GREEN,
    "R":  Fore.RED,
    "Y":  Fore.YELLOW,
    "B":  Fore.BLUE,
    "M":  Fore.MAGENTA,
    "C":  Fore.CYAN,
    "RE": Style.RESET_ALL,
}


def print_table(rows: list[list[str]]) -> None:
    print(tabulate(rows, headers="firstrow", tablefmt="simple_outline"))


def confirm(prompt: str = "Procedere con il lancio dei job? (yes/no): ") -> bool:
    return input(prompt).lower() in ("yes", "y")
