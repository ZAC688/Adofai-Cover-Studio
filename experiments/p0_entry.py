"""PyInstaller entrypoint with Windows multiprocessing support reserved."""
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from experiments.p0 import main
    raise SystemExit(main())
