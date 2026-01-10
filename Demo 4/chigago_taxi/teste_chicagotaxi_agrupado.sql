CREATE OR REPLACE TABLE `br-pruebadeconcepto-cld-01.mprs.teste_chicagotaxi_agrupado` AS
SELECT 
  trip_date,
  COUNT(DISTINCT unique_key) AS unique_trip_count
FROM `br-pruebadeconcepto-cld-01.mprs.teste_transf_chicagotaxi`
GROUP BY trip_date
ORDER BY trip_date;