# Usa uma imagem base Python para maior flexibilidade
FROM python:3.10.15

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia os arquivos de dependências e o script do servidor
COPY requirements.txt predictor.py ./

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta 8080, que é a padrão para o Vertex AI
EXPOSE 8080

# Comando para iniciar o servidor Gunicorn, que roda a aplicação Flask
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "180", "--workers", "1", "predictor:app"]