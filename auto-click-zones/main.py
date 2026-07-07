"""Entry point for Auto Click Zones application."""

import sys


def main() -> None:
    """Launch the Auto Click Zones GUI."""
    from auto_click_zones.config import ensure_runtime_data
    from auto_click_zones.gui import MainWindow

    ensure_runtime_data()
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
    sys.exit(0)
