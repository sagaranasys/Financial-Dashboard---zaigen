import shutil
import zipfile
import os
import pandas as pd
import io

# Definições
source_path = r"C:\Users\glauc\Downloads\extrato-da-sua-conta-01KE9T37DF6QWQGFYFH3X1K668.zip"
dest_path = os.path.join(os.getcwd(), 'uploads', 'extrato_temp.zip')
password = b'399838'

print(f"1. Copiando de: {source_path}")
try:
    shutil.copy2(source_path, dest_path)
    print("   Cópia realizada com sucesso.")
except Exception as e:
    print(f"   Erro ao copiar: {e}")
    exit()

print("\n2. Abrindo ZIP...")
try:
    with zipfile.ZipFile(dest_path, 'r') as zf:
        # Tentar desbloquear
        zf.setpassword(password)
        
        file_list = zf.namelist()
        print(f"   Arquivos encontrados: {file_list}")
        
        target_file = file_list[0]
        print(f"   Analisando arquivo: {target_file}")
        
        with zf.open(target_file) as f:
            # Ler as primeiras linhas para identificar estrutura
            # C6 costuma mandar CSV separado por ; ou ,
            content = f.read()
            
            # Tentar decodificar
            try:
                decoded = content.decode('utf-8')
            except:
                decoded = content.decode('latin-1')
            
            print("\n--- INÍCIO DO ARQUIVO (Primeiras 10 linhas) ---")
            lines = decoded.splitlines()[:10]
            for line in lines:
                print(line)
            print("--- FIM DO ARQUIVO ---\n")
            
            # Tentar carregar com pandas para ver colunas
            try:
                # Tenta detectar separador
                sep = ';' if ';' in lines[5] else ',' 
                # Pular linhas de cabeçalho inúteis se houver (geralmente C6 tem cabeçalho fixo)
                # Vamos tentar ler buffer
                df = pd.read_csv(io.StringIO(decoded), sep=sep, on_bad_lines='skip')
                print("Colunas detectadas pelo Pandas:")
                print(df.columns.tolist())
                print("\nPrimeira linha de dados:")
                print(df.iloc[0].to_dict())
            except Exception as pandas_e:
                print(f"Erro ao ler com pandas: {pandas_e}")

except Exception as e:
    print(f"ERRO: {e}")
