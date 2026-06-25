# Fetch a document's metadata

Fetch a document's metadata

## Request

```
GET https://document-api.company-information.service.gov.uk/document/{document_id}
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| document_id | string | the id of the document | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK Document metadata | [documentMetadata](https://developer-specs.company-information.service.gov.uk/document-api/resources/documentmetadata?v=latest) |
| 401 | Unauthorized Not authorised to retrieve document metadata |  |
