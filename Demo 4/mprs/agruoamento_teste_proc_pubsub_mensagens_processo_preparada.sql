CREATE OR REPLACE TABLE `br-pruebadeconcepto-cld-01.mprs.teste_proc_pubsub_mensagens_processo_preparada_agrupada` AS
SELECT
  data,
  COUNT(DISTINCT numero_processo) AS qtd_distinta_processo
FROM
  `br-pruebadeconcepto-cld-01.mprs.teste_proc_pubsub_mensagens_processo_preparada`
GROUP BY
  data
ORDER BY
  data DESC;