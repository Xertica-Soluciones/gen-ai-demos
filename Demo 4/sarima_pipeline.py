# ============================
# 1. Bibliotecas e configurações
# ============================
from google.cloud import bigquery, storage, aiplatform
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pmdarima import auto_arima
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error
import joblib
import os

# ============================
# 2. Configurações
# ============================
PROJECT_ID = "br-pruebadeconcepto-cld-01"
LOCATION = "southamerica-east1"
BUCKET_NAME = "demo4mldata"
#GCS_MODEL_PATH = "modelos/sarima_model.pkl"
#GCS_YAML_PATH = "modelos/modelo.yaml"
GCS_PREDICTOR_PATH = "modelos/predictor.py"
GCS_REQS_PATH = "modelos/requirements.txt"

#LOCAL_MODEL_FILE = "sarima_model.pkl"
#LOCAL_YAML_FILE = "modelo.yaml"
LOCAL_PREDICTOR_FILE = "predictor.py"
LOCAL_REQUIREMENTS = "requirements.txt"

LOCAL_MODEL_FILE = "model.pkl"
GCS_MODEL_PATH = "modelos/model.pkl"

# ============================
# 3. Coleta de dados do BigQuery
# ============================
print("Carregando dados do BigQuery...")
bq_client = bigquery.Client(project=PROJECT_ID)

query = """
SELECT trip_date, unique_trip_count
FROM `br-pruebadeconcepto-cld-01.mprs.teste_chicagotaxi_agrupado`
ORDER BY trip_date
"""

df = bq_client.query(query).to_dataframe()
df['trip_date'] = pd.to_datetime(df['trip_date'])
df.set_index('trip_date', inplace=True)
df = df.asfreq('D')
df['unique_trip_count'] = df['unique_trip_count'].interpolate()


# ============================
# 4. Treinamento SARIMA
# ============================
print("Treinando modelo SARIMA...")
n_test = 30
train = df['unique_trip_count'][:-n_test]
test = df['unique_trip_count'][-n_test:]

stepwise_model = auto_arima(train,
                             start_p=0, start_q=0,
                             max_p=3, max_q=3,
                             start_P=0, start_Q=0,
                             max_P=2, max_Q=2,
                             d=None, D=None,
                             seasonal=True,
                             m=7,
                             trace=True,
                             error_action='ignore',
                             suppress_warnings=True,
                             stepwise=True)

forecast = stepwise_model.predict(n_periods=n_test)
forecast = pd.Series(forecast, index=test.index)

# ============================
# 5. Avaliação
# ============================
mae = mean_absolute_error(test, forecast)
rmse = np.sqrt(mean_squared_error(test, forecast))
mape = mean_absolute_percentage_error(test, forecast)

print(f"\nMAE: {mae:.2f}")
print(f"RMSE: {rmse:.2f}")
print(f"MAPE: {mape*100:.2f}%")

# ============================
# 6. Salvando o modelo
# ============================
print(f"Salvando modelo localmente em: {LOCAL_MODEL_FILE}")
joblib.dump(stepwise_model, LOCAL_MODEL_FILE)

# ============================
# 7. Previsões futuras
# ============================
n_periods_future = 30
forecast_future, conf_int = stepwise_model.predict(n_periods=n_periods_future, return_conf_int=True)
last_date = df.index[-1]
future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=n_periods_future, freq='D')

forecast_df = pd.DataFrame({
    'data': future_dates,
    'previsao': forecast_future,
    'desvio_padrao': (conf_int[:, 1] - conf_int[:, 0]) / (2 * 1.96),
    'minimo_previsto': conf_int[:, 0],
    'maximo_previsto': conf_int[:, 1]
})

print(forecast_df.head())

# ============================
# 8. Plotagem
# ============================
plt.figure(figsize=(10, 5))
plt.plot(df.index[-30:], df['unique_trip_count'].tail(30), label='Histórico recente')
plt.plot(forecast_df['data'], forecast_df['previsao'], label='Previsão')
plt.fill_between(forecast_df['data'], forecast_df['minimo_previsto'], forecast_df['maximo_previsto'],
                 color='lightblue', alpha=0.5, label='Intervalo de confiança 95%')
plt.legend()
plt.title('Previsão SARIMA com intervalo')
plt.xlabel('Data')
plt.ylabel('unique_trip_count')
plt.grid(True)
plt.tight_layout()
plt.savefig("forecast_plot.png")
plt.show()

# ============================
# 9. Criando o arquivo predictor.py
# ============================
print("Criando arquivo predictor.py...")

predictor_code = '''
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

    def predict(self, instances):
        """
        Faz a previsão usando o modelo SARIMA. O parâmetro 'instances' é ignorado,
        pois o modelo SARIMA continua a série temporal.
        """
        if self.model is None:
            raise RuntimeError("O modelo não foi carregado corretamente.")

        n_periods_to_predict = 12  # Exemplo: prever 12 períodos à frente
        forecast, conf_int = self.model.predict(n_periods=n_periods_to_predict, return_conf_int=True)
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
    if not predictor_instance or predictor_instance.model is None:
        return jsonify({"error": "O modelo não está pronto para previsões."}), 503

    data = request.get_json()
    if not data or "instances" not in data:
        return jsonify({"error": "Corpo da requisição inválido. Espera-se um JSON com a chave 'instances'."}), 400

    try:
        predictions = predictor_instance.predict(data.get("instances"))
        return jsonify(predictions)
    except Exception as e:
        logging.error(f"Erro durante a previsão: {str(e)}")
        return jsonify({"error": f"Falha na previsão: {str(e)}"}), 500
'''

with open(LOCAL_PREDICTOR_FILE, "w") as f:
    f.write(predictor_code.strip())

print("✔ Arquivo predictor.py criado com sucesso.")

# ============================
# 10. Upload de arquivos para o GCS
# ============================
print("Fazendo upload dos arquivos para o Cloud Storage...")
storage_client = storage.Client(project=PROJECT_ID)
bucket = storage_client.bucket(BUCKET_NAME)

def upload_to_gcs(local_path, gcs_path):
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)
    print(f"✔ Enviado: gs://{BUCKET_NAME}/{gcs_path}")

upload_to_gcs(GCS_MODEL_PATH, GCS_MODEL_PATH)
upload_to_gcs(LOCAL_REQUIREMENTS, GCS_REQS_PATH)
upload_to_gcs(LOCAL_PREDICTOR_FILE, GCS_PREDICTOR_PATH)

# # ============================
# # 11. Criando modelo.yaml
# # ============================
# yaml_content = f"""
# name: sarima-model
# description: Modelo SARIMA para previsão de corridas
# artifact_uri: gs://{BUCKET_NAME}/{GCS_MODEL_PATH}
# container_spec:
#   image_uri: us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.0-24:latest
#   command: []
# """

# with open(LOCAL_YAML_FILE, "w") as f:
#     f.write(yaml_content.strip())

# print("✔ Arquivo modelo.yaml criado com sucesso.")

# upload_to_gcs(LOCAL_YAML_FILE, GCS_YAML_PATH)

# ============================
# 12. Registro no Vertex AI
# ============================

print("Registrando modelo no Vertex AI...")

from google.cloud import aiplatform
'''
aiplatform.init(project=PROJECT_ID, location=LOCATION)

model = aiplatform.CustomPythonModel(
    display_name="sarima-model",
    model_path=f"gs://{BUCKET_NAME}/modelos/model.pkl",
    python_package_gcs_uri=f"gs://{BUCKET_NAME}/modelos/",
    serving_container_image_uri="southamerica-east1-docker.pkg.dev/br-pruebadeconcepto-cld-01/vertex-custom-containers/sarima-predictor:latest",
    #serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-0:latest",
    requirements=["pmdarima", "joblib", "numpy"]
)

model.upload()
'''
aiplatform.init(project="br-pruebadeconcepto-cld-01", location="southamerica-east1")

model = aiplatform.Model.upload(
    display_name="sarima-model", 
    #display_name="sarima-model",
    artifact_uri="gs://demo4mldata/modelos/",  # pasta onde está o model.pkl
    serving_container_image_uri="southamerica-east1-docker.pkg.dev/br-pruebadeconcepto-cld-01/vertex-custom-containers/sarima-predictor:latest"
    #serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-0:latest"
)
print(f"✔ Modelo registrado com sucesso! ID: {model.resource_name}")

# ============================
# 13. Criando o Endpoint
# ============================

aiplatform.init(project=PROJECT_ID, location=LOCATION)

# Criar Endpoint
endpoint = aiplatform.Endpoint.create(display_name="sarima-endpoint")
print(f"✔ Endpoint criado: {endpoint.resource_name}")

# Listar todos os modelos
models = aiplatform.Model.list(order_by="create_time desc")

# Buscar o modelo pelo nome
model = next((m for m in models if m.display_name == "sarima-model"), None)
if model is None:
    raise ValueError("❌ Modelo 'sarima-model' não encontrado.")
print(f"✔ Modelo encontrado: {model.resource_name}")

# ============================
# 14. Fazer o deploy no endpoint
# ============================

# model.deploy(
#     endpoint=endpoint,
#     deployed_model_display_name="disp_sarima-model",
#     machine_type="n1-standard-2",
#     traffic_split={"0": 100}
# )

model.deploy(
    endpoint=endpoint,
    deployed_model_display_name="sarima-model",
    machine_type="e2-standard-4",
    traffic_split={"0": 100}
)

# ============================
# 15. Testando a API
# ============================

instances = [[1200, 1300, 1250, 1400, 1350, 1500, 1600, 1550, 1490, 1420, 1380, 1300]]
response = endpoint.predict(instances=instances)
print("📈 Previsão:", response.predictions)

'''
 Resultado esperado
✅ Um endpoint criado no Vertex AI.

✅ Seu modelo pronto para receber chamadas via API.

✅ Possibilidade de testar com o SDK ou via REST (Postman ou cURL).
'''