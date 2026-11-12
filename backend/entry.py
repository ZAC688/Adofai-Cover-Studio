import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        from backend.launcher import main
        raise SystemExit(main())
    except Exception as error:
        import ctypes
        import sys
        import traceback
        from pathlib import Path
        try:
            if '--data-dir' in sys.argv:
                directory = Path(sys.argv[sys.argv.index('--data-dir')+1])
            else:
                from backend.launcher import default_data_dir
                directory = default_data_dir()
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / 'startup-error.log').open('a', encoding='utf-8') as log:
                traceback.print_exc(file=log)
        except Exception:
            pass
        if '--no-browser' not in sys.argv and '--desktop-hidden' not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None, str(error), "ADOFAI 封面制作器启动失败", 16)
        # A handled failure must not trigger PyInstaller's own GUI traceback
        # dialog, especially in --no-browser automation and worker processes.
        raise SystemExit(1)
