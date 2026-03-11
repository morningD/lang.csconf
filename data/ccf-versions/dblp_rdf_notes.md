# DBLP RDF Schema - Venue/Location Analysis

**Date:** 2026-03-04
**Source:** https://dblp.org/rdf/docu/
**SPARQL endpoint:** https://sparql.dblp.org/sparql

## Key Finding: No Dedicated Location Property

The DBLP RDF schema has **no dedicated property** for conference venue, city, or country.
There is no `dblp:venue`, `dblp:location`, `dblp:city`, or `dblp:country` predicate.

## How Location IS Available: Proceedings Title

Conference location is **embedded in the `dblp:title` of Proceedings records**.
The pattern is highly consistent across conferences and years:

```
"Proceedings of ..., {ConferenceName} {Year}, {City}, {Country/State}, {Dates}"
```

### Examples from SPARQL queries

| Conference | Year | Title (location portion) |
|-----------|------|--------------------------|
| EuroSys | 2023 | "...EuroSys 2023, **Rome, Italy**, May 8-12, 2023" |
| EuroSys | 2024 | "...EuroSys 2024, **Athens, Greece**, April 22-25, 2024" |
| EuroSys | 2025 | "...EuroSys 2025, **Rotterdam, The Netherlands**, 30 March..." |
| EuroSys | 2021 | "...EuroSys, **Online Event, United Kingdom**, April 26-28, 2021" |
| CVPR | 2023 | "...CVPR 2023, **Vancouver, BC, Canada**, June 17-24, 2023" |
| CVPR | 2024 | "...CVPR 2024, **Seattle, WA, USA**, June 16-22, 2024" |
| CVPR | 2025 | "...CVPR 2025, **Nashville, TN, USA**, June 11-15, 2025" |
| NeurIPS | 2023 | "...NeurIPS 2023, **New Orleans, LA, USA**, December 10-16, 2023" |
| NeurIPS | 2024 | "...NeurIPS 2024, **Vancouver, BC, Canada**, December 10-15, 2024" |
| ICSE | 2023 | "...ICSE 2023, **Melbourne, Australia**, May 14-20, 2023" |
| ICSE | 2024 | "...ICSE 2024, **Lisbon, Portugal**, April 14-20, 2024" |
| WWW | 2023 | "...WWW 2023, **Austin, TX, USA**, 30 April..." |
| WWW | 2024 | "...WWW 2024, **Singapore**, May 13-17, 2024" |
| SIGCOMM | 2019 | "...SIGCOMM 2019, **Beijing, China**, August 19-23, 2019" |
| SIGCOMM | 2024 | "...SIGCOMM 2024, **Sydney, NSW, Australia**, August 4-8, 2024" |

### COVID-era virtual conferences
Virtual events are indicated in the title as well:
- EuroSys 2021: "Online Event, United Kingdom"
- SIGCOMM 2020: "Virtual Event, USA"
- SIGCOMM 2021: "Virtual Event, USA"

## SPARQL Query to Get Proceedings Titles

```sparql
PREFIX dblp: <https://dblp.org/rdf/schema#>
SELECT ?year ?title WHERE {
  ?proc dblp:bibtexType <http://purl.org/net/nknouf/ns/bibtex#Proceedings> .
  ?proc dblp:publishedInStream <https://dblp.org/streams/conf/{dblp_key}> .
  ?proc dblp:title ?title .
  ?proc dblp:yearOfPublication ?year .
} ORDER BY ?year
```

### Multi-conference batch query

```sparql
PREFIX dblp: <https://dblp.org/rdf/schema#>
SELECT ?stream ?year ?title WHERE {
  VALUES ?stream {
    <https://dblp.org/streams/conf/cvpr>
    <https://dblp.org/streams/conf/nips>
    <https://dblp.org/streams/conf/icse>
  }
  ?proc dblp:bibtexType <http://purl.org/net/nknouf/ns/bibtex#Proceedings> .
  ?proc dblp:publishedInStream ?stream .
  ?proc dblp:title ?title .
  ?proc dblp:yearOfPublication ?year .
  FILTER(?year >= "2020"^^<http://www.w3.org/2001/XMLSchema#gYear>)
} ORDER BY ?stream ?year
```

## Other Properties on Proceedings Records

From inspecting `https://dblp.org/rec/conf/eurosys/2023`:

| Property | Value | Notes |
|----------|-------|-------|
| `rdf:type` | `dblp:Editorship`, `dblp:Publication` | NOT `dblp:Proceedings` class (uses bibtexType) |
| `dblp:bibtexType` | `bibtex:Proceedings` | This is how to filter for proceedings |
| `dblp:title` | Full title with location | **Primary source of location info** |
| `rdfs:label` | Same as title + author prefix | e.g. "Giuseppe Antonio Di Luna et al.: Proceedings..." |
| `dblp:publishedInStream` | Stream URI | Links to conference series |
| `dblp:publishedBy` | "ACM" | Publisher name |
| `dblp:yearOfPublication` | xsd:gYear | e.g. "2023" |
| `dblp:editedBy` / `dblp:createdBy` | Creator URIs | Proceedings editors |
| `dblp:doi` | DOI URI | |
| `dblp:isbn` | ISBN URN | |
| `dblp:numberOfCreators` | int | Number of editors |
| `dblp:listedOnTocPage` | DBLP ToC page URI | |
| `dblp:documentPage` | DOI URL | |
| `dblp:primaryDocumentPage` | DOI URL | |
| `dblp:hasSignature` | blank nodes | Author signature objects |
| `datacite:hasIdentifier` | blank nodes | Identifier objects |
| `owl:sameAs` | DOI, ISBN, Wikidata URIs | |

## `publishersAddress` Property

This property exists in the schema but is extremely rare in practice. Only 3 results
found across the entire DBLP dataset, all from 1977-1982 database workshops with value "New York"
(referring to the publisher's address, not the conference venue). **Not useful for venue extraction.**

## Complete DBLP RDF Schema Properties (78 total)

### Publication properties
- `authoredBy`, `createdBy`, `editedBy` - link to Creator
- `title`, `pagination`, `publicationNote` - string literals
- `yearOfEvent`, `yearOfPublication`, `monthOfPublication` - date/int
- `publishedIn`, `publishedInBook`, `publishedInJournal` - string/entity
- `publishedInStream` - link to Stream (conference series)
- `publishedInSeries`, `publishedInSeriesVolume` - series info
- `publishedInJournalVolume`, `publishedInJournalVolumeIssue` - journal info
- `publishedInBookChapter` - book chapter info
- `publishedAsPartOf` - link to parent publication (e.g. paper -> proceedings)
- `publishedBy`, `publishersAddress` - publisher info (address is rare)
- `doi`, `isbn`, `omid`, `wikidata` - identifiers
- `documentPage`, `primaryDocumentPage` - URLs
- `listedOnTocPage` - DBLP table of contents page
- `bibtexType` - BibTeX entry type
- `numberOfCreators` - int
- `hasSignature` - author signature objects
- `hasVersion`, `isVersion`, `isVersionOf` - versioning
- `thesisAcceptedBySchool` - thesis-specific

### Creator properties
- `creatorName`, `primaryCreatorName` - names
- `affiliation`, `primaryAffiliation` - affiliations (string)
- `orcid` - ORCID identifier
- `homepage`, `primaryHomepage`, `webpage`, `awardWebpage` - URLs
- `authorOf`, `creatorOf`, `editorOf` - inverse of publication links
- `coAuthorWith`, `coCreatorWith`, `coEditorWith` - co-authorship
- `homonymousCreator`, `proxyAmbiguousCreator`, `possibleActualCreator` - disambiguation
- `creatorNote` - notes

### Stream (Conference/Journal series) properties
- `streamTitle`, `primaryStreamTitle`, `formerStreamTitle` - names
- `indexPage` - DBLP index page
- `iso4` - ISO 4 abbreviation
- `issn` - ISSN
- `subStream`, `superStream` - hierarchy
- `predecessorStream`, `successorStream` - temporal succession
- `relatedStream` - related series

### Signature properties
- `signatureCreator`, `signatureDblpName`, `signatureOrcid`, `signatureOrdinal`, `signaturePublication`

### Version properties
- `versionConcept`, `versionInstance`, `versionLabel`, `versionOrdinal`, `versionUri`

### General
- `identifier`, `archivedWebpage`, `webpage`, `wikidata`, `wikipedia`

## Practical Notes for lang.csconf

### Extracting location from proceedings titles

To get venue info, you would:
1. Query for Proceedings records (filter by `bibtexType = bibtex:Proceedings`)
2. Extract the `title` field
3. Parse the city/country from the title string using regex or heuristics

**Common title patterns:**
```
"...Conference Name YEAR, City, Country, Dates"
"...Conference Name YEAR, City, State, Country, Dates"
"...Conference Name YEAR, City, State/Province, Country, Dates"
"...Virtual Event, Country, Dates"    # COVID-era
```

**Challenges:**
- Format is not 100% standardized (varies by publisher)
- Some titles have the location before or after the conference abbreviation
- "Virtual Event" / "Online Event" during COVID years
- Some proceedings may not include location at all
- Multiple proceedings per conf-year (main + companion + workshops)

### Note on `yearOfEvent` vs `yearOfPublication`

- `yearOfEvent` appears on **Inproceedings** (individual papers), typed as `xsd:gYear`
- `yearOfPublication` appears on **Proceedings** (the proceedings record itself)
- When querying proceedings, use `yearOfPublication`
- When filtering by year, must cast: `FILTER(?year = "2023"^^xsd:gYear)` or compare as strings
