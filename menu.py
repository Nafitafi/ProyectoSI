"""
Menu principal para seleccionar entre cliente TCP y UDP. Importa herramientas
para limpiar la pantalla, controlar el sistema y correr el programa.

Cabe aclarar que se pueden ejecutar los archivos menu.py y servidores.py sin entrar a la interfaz grafica. Por lo tanto, se ejecuta primero servidores.py 
y despues el menu.py donde te dara opciones del cliente a correr deseado.

- import os para usar funciones del sistema operativo de tal manera que se pueda limpiar la pantalla
- import subprocess para ejecutar otros programas desde este script
- import sys para interactuar con el interprete de Python y salir del programa cuando se desee
"""

import os #importa el modulo os para usar funciones del sistema operativo 
import subprocess #importa subprocess para ejecutar otros programas
import sys 

def limpiar():
    """
    Limpia la pantalla de la terminal, dependiendo del sistema operativo: 
    'cls' para Windows y 'clear' para Unix/Linux/Mac."""
    os.system("cls" if os.name == "nt" else "clear")


def menu_principal():
    """
    Muestra el menú principal para ejecutar el cliente TCP o salir.
    """
    while True:
        limpiar()
        print("SELECCIONA UNA OPCIÓN")
        print("1. Iniciar Cliente TCP (Terminal)")
        print("2. Salir\n")
        
        opcion = input("Elige una opción: ").strip()

        if opcion == "1":
            ejecutar_cliente("cliente_tcp.py")
        elif opcion == "2":
            print("Saliendo del programa")
            sys.exit(0)
        else:
            input("Opción inválida. Presiona ENTER para continuar")


def ejecutar_cliente(archivo):
    """
    Ejecuta el cliente especificado (TCP o UDP) y espera a que termine antes de volver al menú principal
    
    """
    limpiar()
    print(f"[MENÚ] Ejecutando {archivo}...\n")

    try:
        subprocess.run([sys.executable, archivo])
    except Exception as e:
        print(f"[ERROR] No se pudo ejecutar {archivo}: {e}")

    input("\nEl cliente terminó. Presiona ENTER para volver al menú principal")


if __name__ == "__main__":
    menu_principal()
