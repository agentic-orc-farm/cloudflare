"""Run `python -m cf_plane`, which is the same as the `cf-plane` command."""

import sys

from cf_plane.cli import main

sys.exit(main())
