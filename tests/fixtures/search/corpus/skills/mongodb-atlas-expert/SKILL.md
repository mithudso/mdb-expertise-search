# MongoDB Atlas

## Private Endpoints

Atlas private endpoints use AWS PrivateLink, Azure Private Link or GCP Private Service Connect so that
application traffic never crosses the public internet. Each endpoint is regional.

## Atlas Vector Search

$vectorSearch runs an approximate nearest-neighbour search. numCandidates controls recall versus
latency; a value of 10 to 20 times the limit is a common starting point. Pre-filter fields must be
indexed as filter fields in the vector index definition.

## Performance Advisor

The Performance Advisor ranks slow query shapes and suggests indexes by impact. Treat each suggestion
as evidence and confirm it with explain().
