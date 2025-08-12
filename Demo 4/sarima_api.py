from google.cloud import aiplatform

def predict_custom_trained_model(
    project: str,
    location: str,
    endpoint_id: str,
    instances: list
):
    """
    Chama um endpoint da Vertex AI para obter uma predição.

    Args:
        project (str): O ID do seu projeto no Google Cloud.
        location (str): A região onde seu endpoint está localizado.
        endpoint_id (str): O ID do seu endpoint.
        instances (list): Uma lista de listas com os dados para a predição.
    """
    # Inicializa o SDK da Vertex AI
    aiplatform.init(project=project, location=location)

    # Cria um objeto Endpoint apontando para o seu modelo
    endpoint = aiplatform.Endpoint(endpoint_name=endpoint_id)

    # Envia a requisição de predição
    # O SDK formata automaticamente a lista de instâncias para a API
    response = endpoint.predict(instances=instances)
    
    # Imprime a resposta completa e o ID do modelo
    # print("Resposta completa:", response)
    # print("="*30)
    # print("📈 Previsão:", response.predictions)
    # print("ID do modelo implantado:", response.deployed_model_id)

    return response


# --- Suas informações ---
project_id = "538940429074"
endpoint_id = "8616041396089913344"
location = "southamerica-east1"

# Os dados de entrada para o modelo
# Note que passamos diretamente a lista de listas, como o modelo espera.
instances_data = [[1200, 1300, 1250, 1400, 1350, 1500, 1600, 1550, 1490, 1420, 1380, 1300]]

# --- Chamada da função ---
predict_custom_trained_model(
    project=project_id,
    location=location,
    endpoint_id=endpoint_id,
    instances=instances_data,
)