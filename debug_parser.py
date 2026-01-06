# -*- coding: utf-8 -*-
from processors.csv_parser import parse_valor_monetario

test_values = [
    "550,00",
    "5,50", 
    "1.000,00",
    "1000,00",
    "-550,00",
    "3.416.346,00", 
    "34163,46"
]

print("Teste de parse_valor_monetario com a implementação ATUAL:")
for val in test_values:
    parsed = parse_valor_monetario(val)
    print(f"'{val}' -> {parsed}")
