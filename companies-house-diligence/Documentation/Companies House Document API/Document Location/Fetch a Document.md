# Fetch a document

Fetch a document

## Request

```
GET https://document-api.company-information.service.gov.uk/document/{document_id}/content
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| document_id | string | the id of the document | Required |

## Request headers

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| Accept | string | Gives the Content-Type that the document will be returned as. If the Content-Type is unsupported, a 406 error will be generated. The Content-Types that the document is available as can be found by requesting the metadata for the document. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 302 | Found Document location |  |
| 401 | Unauthorized Not authorised to retrieve document |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| Location | string | A redirect is being made to the resource to be returned |
