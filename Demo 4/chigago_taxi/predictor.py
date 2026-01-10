import joblib
import numpy as np
import os
import logging
from pmdarima.arima import ARIMA
from flask import Flask, request, jsonify
from google.cloud import storage

# Configura o logger
logging.basicConfig(level=logging.INFO)

class Predictor:
    """
    Classe para carregar o modelo SARIMA e fazer previsões.
    """
    def __init__(self, model_dir):
        self.model = None
        # A variável de ambiente AIP_STORAGE_URI aponta para o diretório de artefatos
        gcs_uri = os.environ.get("AIP_STORAGE_URI")
        local_model_path = os.path.join(model_dir, "model.pkl")

        if gcs_uri:
            try:
                logging.info(f"Iniciando download do modelo do GCS: {gcs_uri}")
                # Remove o prefixo "gs://" da URI
                uri_path = gcs_uri[5:]
                bucket_name = uri_path.split('/')[0]
                blob_prefix = '/'.join(uri_path.split('/')[1:])
                
                # Constrói o caminho completo do blob
                full_blob_path = os.path.join(blob_prefix, "model.pkl")
                
                storage_client = storage.Client()
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(full_blob_path)
                
                # Baixa o modelo do GCS para o diretório local do contêiner
                blob.download_to_filename(local_model_path)
                logging.info("✔ Download do modelo concluído com sucesso.")
                
                self.model = joblib.load(local_model_path)
                logging.info("✔ Modelo SARIMA carregado com sucesso.")
            except Exception as e:
                logging.error(f"❌ Erro ao carregar o modelo do GCS: {str(e)}")
                self.model = None
        else:
            # Lógica para carregar localmente (teste local)
            try:
                logging.info(f"Carregando modelo localmente de: {local_model_path}")
                self.model = joblib.load(local_model_path)
                logging.info("✔ Modelo SARIMA carregado com sucesso localmente.")
            except Exception as e:
                logging.error(f"❌ Erro ao carregar o modelo localmente: {str(e)}")
                self.model = None

    def predict(self, n_periods: int):
        """
        Faz a previsão usando o modelo SARIMA para um número especificado de períodos.
        """
        if self.model is None:
            raise RuntimeError("O modelo não foi carregado corretamente.")

        forecast, conf_int = self.model.predict(n_periods=n_periods, return_conf_int=True)
        return {
            "predictions": forecast.tolist(),
            "confidence_interval": conf_int.tolist()
        }

# Inicializa a aplicação Flask e a instância do predictor
app = Flask(__name__)
model_dir = os.environ.get("AIP_MODEL_DIR", ".")
predictor_instance = Predictor(model_dir)

@app.route(os.environ.get("AIP_HEALTH_ROUTE", "/health"), methods=["GET"])
def health_check():
    """Endpoint de verificação de saúde."""
    if predictor_instance and predictor_instance.model is not None:
        logging.info("✔ Health check bem-sucedido. O modelo está pronto.")
        return "ok", 200
    else:
        logging.warning("⚠️ Health check falhou. O modelo ainda não está pronto.")
        return "Not OK - Model not loaded", 503

@app.route(os.environ.get("AIP_PREDICT_ROUTE", "/predict"), methods=["POST"])
def predict_route():
    """Endpoint para predições."""
    if not predictor_instance or predictor_instance.model is None:
        return jsonify({"error": "O modelo não está pronto para previsões."}), 503

    data = request.get_json()
    
    # Verifica se a requisição contém a chave 'instances' e se ela não está vazia
    if not data or "instances" not in data or not data["instances"]:
        return jsonify({
            "error": "Corpo da requisição inválido. Espera-se um JSON com a chave 'instances' contendo 'n_periods'."
        }), 400

    try:
        # Extrai o valor de 'n_periods' da primeira instância da lista
        # A requisição deve ser: {"instances": [{"n_periods": 12}]}
        n_periods = data["instances"][0].get("n_periods")
        
        # Validação simples para garantir que o valor é um inteiro positivo
        if not isinstance(n_periods, int) or n_periods <= 0:
            return jsonify({
                "error": "Valor para 'n_periods' inválido. Espera-se um inteiro positivo."
            }), 400

        # Chama o método predict com o novo valor
        predictions = predictor_instance.predict(n_periods)
        return jsonify(predictions)
    except Exception as e:
        logging.error(f"Erro durante a previsão: {str(e)}")
        return jsonify({"error": f"Falha na previsão: {str(e)}"}), 500