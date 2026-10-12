import argparse
import json
import logging
import os
import sys
import time
from .config import load
from .api import Controller, SpiceClient, APIError


def main():
    parser = argparse.ArgumentParser(description="Local/offline screen reader; dry-run by default")
    parser.add_argument("--config",default="config.example.json")
    sub = parser.add_subparsers(dest="command",required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--output",default="demo-output")
    demo.add_argument("--show",action="store_true")
    cal = sub.add_parser("calibrate")
    cal.add_argument("--image",help="Already-cropped ROI image; ROI origin remains as configured")
    cal.add_argument("--output",default="config.local.json")
    sub.add_parser("discover")
    sub.add_parser("reset",help="Explicitly reset configured controls only")
    run = sub.add_parser("run")
    run.add_argument("--live",action="store_true")
    run.add_argument("--offline-confirmed",action="store_true")
    run.add_argument("--experimental-lasers",action="store_true",help="Acknowledge unverified game-specific knob response")
    run.add_argument("--seconds",type=float,default=30)
    run.add_argument("--no-preview",action="store_true")
    run.add_argument("--output",default="run-events.json")
    chart = sub.add_parser("chart")
    chart.add_argument("path")
    sync = sub.add_parser("sync")
    sync.add_argument("path")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,format="%(levelname)s: %(message)s")
    client = None
    control = None
    try:
        if args.command in {"chart","sync"}:
            from .charts import parse_ksh,parse_vox,fit_sync
            fn = fit_sync if args.command == "sync" else parse_ksh if args.path.lower().endswith(".ksh") else parse_vox
            print(json.dumps(fn(args.path),indent=2))
            return 0
        cfg = load(args.config)
        if args.command == "demo":
            from .demo import run
            run(cfg,args.output,args.show)
        elif args.command == "calibrate":
            from .calibrate import calibrate
            calibrate(cfg,args.output,args.image)
        else:
            live = args.command in {"discover","reset"} or args.live
            if args.command == "run":
                if not 0 < args.seconds <= 600:
                    raise ValueError("Run length must be in (0,600] seconds")
                if not cfg["geometry"]["calibrated"]:
                    raise ValueError("Calibrate the actual playfield first")
                if args.live and not args.offline_confirmed:
                    raise ValueError("Live input requires --offline-confirmed after isolating the game from online services")
            if live:
                api = cfg["api"]
                client = SpiceClient(api["host"],api["port"],os.environ.get(api["password_env"],""),api["timeout"])
            control = Controller(client)
            if args.command == "discover":
                print(json.dumps(control.discover(),indent=2))
            elif args.command == "reset":
                client.call("buttons","write_reset",[[n] for n in cfg["buttons"]])
                client.call("analogs","write_reset",[[n] for n in cfg["analogs"]])
                print("Configured overrides reset")
            else:
                from .runtime import run
                control.validate(cfg["buttons"],cfg["analogs"] if cfg["laser"]["enabled"] else [])
                if client and cfg["laser"]["enabled"] and not args.experimental_lasers:
                    raise ValueError("Live lasers require --experimental-lasers; knob gain/direction are unverified for your build")
                print("Starting in 3 seconds; F12 stops. Keep the game on an offline practice playfield.")
                time.sleep(3)
                run(cfg,control,args.seconds,args.output,not args.no_preview)
        return 0
    except (APIError,OSError,ValueError,KeyError,ImportError) as exc:
        logging.error("%s",exc)
        return 1
    except KeyboardInterrupt:
        logging.warning("Interrupted")
        return 130
    finally:
        if control:
            try:
                control.reset(terminal=True)
            except APIError as exc:
                logging.error("%s",exc)
        if client:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
