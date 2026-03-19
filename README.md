# Maps of Armenia in Trove

This repository contains a dataset of **metadata records for maps related to Armenia** collected from Trove (National Library of Australia).

The dataset was compiled for **Open Data Armenia** as part of its broader effort to identify, collect, document, and preserve Armenian cultural heritage across international archives, libraries, and digital collections.


## Data Source

**Source:** Trove (National Library of Australia)  
**Platform:** https://trove.nla.gov.au

Trove is the discovery platform of the National Library of Australia and provides access to records from Australian libraries, archives, museums, and other partner institutions.

This repository focuses on records from the **Images, Maps & Artefacts** section, specifically items filtered as **maps**.

## Dataset Contents

The dataset contains **metadata only**.  
It does **not** reproduce the original maps.

Each row describes one Trove record and may include:

- title
- date or period
- author or creator
- description or abstract
- URL to original object
- manuscript ID or shelfmark
- Trove category
- Trove record type
- Trove ID
- Trove URL

## Main Data File

`data/trove_armenia_maps.csv`

## Methodology

The dataset was collected through the Trove API by querying the Trove **image** category and filtering for records in the **map** format connected to Armenia.

The extraction workflow includes:

- API-based collection
- pagination through result pages
- metadata normalization
- cleaning of bracketed and nested fields
- export to CSV/JSONL

## Project Context

This dataset was prepared for **Open Data Armenia** in order to support the documentation of Armenian historical and cultural heritage represented in global digital collections.

## Suggested Use Cases

This dataset may support research in:

- Armenian historical geography
- cartographic history
- digital humanities
- Armenian studies
- archival discovery and heritage mapping

## Data Rights and Attribution

This repository contains **metadata only** collected from Trove.

Please see [DATA_RIGHTS.md](DATA_RIGHTS.md) for the attribution and rights statement.

