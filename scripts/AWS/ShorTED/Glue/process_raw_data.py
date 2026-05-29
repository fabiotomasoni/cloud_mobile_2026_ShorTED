import sys
import json
import boto3

from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import col, collect_list, first

args = getResolvedOptions(sys.argv, ['JOB_NAME'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Configurazioni Bucket S3
raw_bucket = "project-tedx-raw-data"
processed_bucket = "project-tedx-processed-data"
raw_path = "s3://" + raw_bucket + "/"
output_prefix = "videos/"

# Lettura dei file CSV con opzioni per gestire testi complessi e virgole interne
read_options = {"header": "true", "quote": "\"", "escape": "\"", "multiLine": "true"}

final_list = spark.read.options(**read_options).csv(raw_path + "final_list.csv")
details = spark.read.options(**read_options).csv(raw_path + "details.csv")
tags = spark.read.options(**read_options).csv(raw_path + "tags.csv")
related_videos = spark.read.options(**read_options).csv(raw_path + "related_videos.csv")
images = spark.read.options(**read_options).csv(raw_path + "images.csv")

# Raggruppamento e aggregazione dati
tags_grouped = tags.groupBy("id").agg(
    collect_list("tag").alias("tags")
)

related_grouped = related_videos.groupBy("id").agg(
    collect_list("related_id").alias("related_videos")
)

images_grouped = images.groupBy("id").agg(
    first("url").alias("image")
)

# Join 
base_data = final_list.join(
    details.select("id", "duration", "presenterDisplayName"),
    "id",
    "left"
).join(
    tags_grouped,
    "id",
    "left"
).join(
    related_grouped,
    "id",
    "left"
).join(
    images_grouped,
    "id",
    "left"
)


# Elaborazione parallela sui nodi Worker

def process_partition(partition):
    import boto3
    import json
    
    # Inizializzazione client S3 locale al worker
    s3 = boto3.client("s3")
    raw_bucket_local = "project-tedx-raw-data"
    processed_bucket_local = "project-tedx-processed-data"
    output_prefix_local = "videos/"

    def read_transcriptions(video_id):
        transcriptions = {}

        response = s3.list_objects_v2(
            Bucket=raw_bucket_local,
            Prefix="transcriptions/" + str(video_id) + "_"
        )

        if "Contents" not in response:
            return transcriptions

        for obj in response["Contents"]:
            key = obj["Key"]

            if not key.endswith("_raw.json"):
                continue

            file_obj = s3.get_object(Bucket=raw_bucket_local, Key=key)
            content = file_obj["Body"].read().decode("utf-8")
            raw_json = json.loads(content)

            translation = raw_json.get("data", {}).get("translation", {})
            language_info = translation.get("language", {})

            language_code = language_info.get("internalLanguageCode")
            language_name = language_info.get("englishName")

            sentences = []
            raw_text_parts = []

            paragraphs = translation.get("paragraphs", [])

            for paragraph in paragraphs:
                cues = paragraph.get("cues", [])

                for cue in cues:
                    text = cue.get("text", "")
                    timestamp = cue.get("time", "")

                    clean_text = text.replace("\n", " ")

                    sentences.append({
                        "timestamp": str(timestamp),
                        "text": clean_text
                    })

                    raw_text_parts.append(clean_text)

            if language_code is not None:
                transcriptions[language_code] = {
                    "language": language_name,
                    "sentences": sentences,
                    "raw": " ".join(raw_text_parts)
                }

        return transcriptions

    # Funzione di supporto per evitare crash se arrivano testi invece di numeri
    def safe_int(value):
        if value is None:
            return None
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return None

    # Iterazione sulle singole righe 
    for row in partition:
        video_id = safe_int(row["id"])
        
        # Se l'ID è rotto o inesistente, saltiamo questa riga per evitare file JSON sballati
        if video_id is None:
            continue

        speakers = []
        if row["speakers"] is not None:
            speakers = [s.strip() for s in row["speakers"].split(",")]

        # Pulizia sicura dei video correlati
        safe_related_videos = []
        if row["related_videos"] is not None:
            safe_related_videos = [safe_int(x) for x in row["related_videos"] if safe_int(x) is not None]

        # Costruzione del JSON finale per il video con cast sicuri
        result = {
            "id": video_id,
            "title": str(row["title"]) if row["title"] else None,
            "slug": str(row["slug"]) if row["slug"] else None,
            "url": str(row["url"]) if row["url"] else None,
            "duration": safe_int(row["duration"]),
            "tags": row["tags"] if row["tags"] is not None else [],
            "related_videos": safe_related_videos,
            "presenterDisplayName": str(row["presenterDisplayName"]) if row["presenterDisplayName"] else None,
            "speakers": speakers,
            "image": str(row["image"]) if row["image"] else None,
            "transcriptions": read_transcriptions(video_id)
        }

        output_key = output_prefix_local + str(video_id) + ".json"

        # Scrittura del risultato sul bucket S3 dei dati processati
        s3.put_object(
            Bucket=processed_bucket_local,
            Key=output_key,
            Body=json.dumps(result, ensure_ascii=False, indent=4),
            ContentType="application/json"
        )

# Lancio dell'elaborazione distribuita
base_data.foreachPartition(process_partition)

job.commit()