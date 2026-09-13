"""Ponto de entrada usado pelo Vercel (build serverless).

O Vercel exige um arquivo com uma variável de módulo `app` do Flask
definida de forma incondicional (fora de qualquer `if`) para detectar
o app automaticamente. Este arquivo existe só para isso; o app.py
continua sendo o app "de verdade" usado tanto localmente quanto na nuvem.
"""

from app import create_app

app = create_app()
