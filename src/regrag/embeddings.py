"""Azure OpenAI embeddings."""
from regrag.sources import ACTS


def embedding_text(unit: dict) -> str:
    """Text embedded for a unit: act, citation label and article title give context."""
    act = ACTS[unit["act"]].short_name if unit["act"] in ACTS else unit["act"]
    title = f" - {unit['article_title']}" if unit.get("article_title") else ""
    return f"{act} {unit['label']}{title}\n{unit['text']}"


class AzureEmbedder:
    def __init__(self, client, deployment: str, dimensions: int = 1536, batch_size: int = 64):
        self.client = client
        self.deployment = deployment
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.tokens = 0

    @property
    def identity(self) -> str:
        """Changes whenever stored vectors would stop matching query vectors."""
        return f"{self.deployment}:{self.dimensions}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            response = self.client.embeddings.create(model=self.deployment, input=batch,
                                                     dimensions=self.dimensions)
            data = sorted(response.data, key=lambda item: item.index)
            if len(data) != len(batch):
                raise RuntimeError("Embedding response size does not match the request")
            vectors.extend(item.embedding for item in data)
            if getattr(response, "usage", None):
                self.tokens += response.usage.total_tokens
        return vectors
