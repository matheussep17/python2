import sys
import threading

from app.single_instance import acquire_single_instance_lock


if not acquire_single_instance_lock():
    sys.exit(0)

if __name__ == "__main__":
    from app.splash import SplashScreen

    splash = SplashScreen()
    imported = {}

    def load_application():
        try:
            from app.main import main as application_main

            imported["main"] = application_main
        except Exception as exc:
            imported["error"] = exc
        splash.root.after(0, start_application)

    def start_application():
        error = imported.get("error")
        if error is not None:
            splash.set_status("Não foi possível iniciar o aplicativo.")
            splash.root.after(1800, splash.close)
            raise error

        imported["main"](splash=splash)

    splash.set_status("Carregando módulos do aplicativo...")
    threading.Thread(target=load_application, daemon=True).start()
    splash.root.mainloop()
