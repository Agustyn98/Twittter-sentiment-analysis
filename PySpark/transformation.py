from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, when
from pyspark.sql.types import ArrayType, FloatType
from google.cloud import language_v1

import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="/home/agus/programas/sentyment_analysys_project/avid-streamer-351318-ddadcd004872.json"

def analize_text(text):
    client = language_v1.LanguageServiceClient()

    document = language_v1.Document(
        content=text, type_=language_v1.Document.Type.PLAIN_TEXT
    )

    sentiment = client.analyze_sentiment(
        request={"document": document}
    ).document_sentiment

    return (sentiment.score, sentiment.magnitude)


spark = SparkSession.builder.appName("sentyment analysis").getOrCreate()


def get_sentyment(text):
    score, magnitude = analize_text(text)
    #score, magnitude = (-0.1, 0.5)
    return [score, magnitude]


def main():
    sentyment_udf = udf(get_sentyment, ArrayType(FloatType()))

    csv_file = "gs://tweets_datalake1/tweets.csv"
    #csv_file = "/tmp/tweets.csv"

    data = (
        spark.read.option("multiline", True)
        .option("escape", '"')
        .csv(csv_file, header=True)
    )

    data = data.select(
        "id", "name", "text", "date", sentyment_udf(data["text"]).alias("results")
    )

    data = data.withColumn("score", data["results"].getItem(0))
    data = data.withColumn("magnitude", data["results"].getItem(1))
    data = data.withColumn(
        "sentiment",
        when(data["score"] >= 0.2, "positive")
        .when(data["score"] <= -0.2, "negative" )
        .when((data["score"] >= 0.1) & (data["magnitude"] >= 0.5), "positive")
        .when((data["score"] <= -0.1) & (data["magnitude"] >= 0.5), "negative")
        .otherwise("neutral"),
    )
    data = data.drop("results")

    print("RESULTS")
    data.show()
    print("END RESULTS")

    data.write.format("bigquery").option(
        "temporaryGcsBucket", "tweets_datalake1"
    ).option("table", "twitter.tweets").mode("append").save()


if __name__ == "__main__":
    main()
