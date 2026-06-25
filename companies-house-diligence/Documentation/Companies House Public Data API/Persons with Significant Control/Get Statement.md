# Get the person with significant control statement

Get details of a person with significant control statement

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/persons-with-significant-control-statements/{statement_id}
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number of the persons with significant control statements list being requested. | Required |
| statement_id | string | The id of the person with significant control statement details being requested. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK PSCStatement resource returned | [statement](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/statement?v=latest) |
| 401 | Unauthorized Unauthorised |  |
| 404 | Not Found Resource not found |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
