# -*- coding: utf-8 -*-
import os
import shutil

sandbox_dir = "./webapp_sandbox"
live_dir = "./webapp"

if not os.path.exists(sandbox_dir):
    print("Помилка: Папку webapp_sandbox не знайдено!")
    exit(1)

files = ["index.html", "admin.html", "client.js", "admin.js", "style.css"]

for f in files:
    src = os.path.join(sandbox_dir, f)
    dst = os.path.join(live_dir, f)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"Перенесено: {f} -> {dst}")
    else:
        print(f"Пропущено (файл відсутній у сендбоксі): {f}")

print("\nУспіх: Зміни дизайну успішно перенесені в робочу директорію! 🎉")
