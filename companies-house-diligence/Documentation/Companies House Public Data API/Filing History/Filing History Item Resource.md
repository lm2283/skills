# filingHistoryItem resource

Get the filing history item of a company

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/filing-history/{transaction_id}
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number that the single filing is required for. | Required |
| transaction_id | string | The transaction id that the filing history is required for. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK Filing history items resource returned | [filingHistoryItem](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/filinghistoryitem?v=latest) |
| 401 | Unauthorized Unauthorised | [error](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/error?v=latest) |
| 404 | Not Found Filing history not available for this company |  |
