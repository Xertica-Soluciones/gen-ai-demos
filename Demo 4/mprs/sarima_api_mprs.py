from google.cloud import aiplatform

def predict_custom_trained_model(
    project: str,
    location: str,
    endpoint_id: str,
    n_periods: int
):
    """
    Chama um endpoint da Vertex AI para obter uma predição de série temporal.

    Args:
        project (str): O ID do seu projeto no Google Cloud.
        location (str): A região onde seu endpoint está localizado.
        endpoint_id (str): O ID do seu endpoint.
        n_periods (int): O número de períodos futuros para prever.
    """
    # Inicializa o SDK da Vertex AI
    aiplatform.init(project=project, location=location)

    # Cria um objeto Endpoint apontando para o seu modelo
    endpoint = aiplatform.Endpoint(endpoint_name=endpoint_id)

    # Constrói o payload 'instances' no formato que a sua API agora espera
    # O valor de n_periods é encapsulado em um dicionário dentro de uma lista
    instances_payload = [{"n_periods": n_periods}]

    # Envia a requisição de predição com o novo payload
    response = endpoint.predict(instances=instances_payload)
    
    # Imprime a resposta completa e o ID do modelo
    print("Resposta completa:", response)
    print("="*30)
    print("📈 Previsão:", response.predictions)
    print("ID do modelo implantado:", response.deployed_model_id)


# --- Suas informações ---
project_id = "538940429074"
endpoint_id = "887582960545431552"
location = "southamerica-east1"

# Defina o número de períodos que você quer prever
periods_to_predict = 12

# --- Chamada da função ---
# Agora, a função recebe o número de períodos diretamente
predict_custom_trained_model(
    project=project_id,
    location=location,
    endpoint_id=endpoint_id,
    n_periods=periods_to_predict,
)