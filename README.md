Este MVP consulta datos públicos (liquidez/volumen/precio vía DexScreener, holders vía Ethplorer) y calcula un puntaje 1–5 por categoría según tu checklist. Luego entrega:





\- Tabla de puntajes por categoría

\- Promedio total y recomendación (🚫 Evitar / ⚠️ Especulativo / ✅ Aceptable)





\## Estructura

```

.

├── requirements.txt

├── config.toml # copia desde config.example.toml y pon tus claves si quieres

├── main.py # entrada principal

├── scoring.py # reglas de puntaje

└── providers/

├── \_\_init\_\_.py

├── dexscreener.py # liquidez, volumen, pares

└── ethplorer.py # top holders, supply (Ethereum/ETH tokens)

```





\## Instalación rápida

1\) Crea un entorno (opcional) y instala dependencias:

```

pip install -r requirements.txt

```

2\) Copia `config.example.toml` a `config.toml` (opcional). Para este MVP \*\*no es obligatorio\*\* porque usamos Ethplorer `freekey`.





3\) Ejecuta (ejemplos):

```

python main.py --chain ethereum --token 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48

python main.py --chain ethereum --pair https://dexscreener.com/ethereum/0xADDRESS\_DEL\_PAIR

```





> Consejo: si tienes el \*\*contrato del token\*\*, usa `--token`. Si tienes el \*\*par en DexScreener\*\*, usa `--pair`.





---

