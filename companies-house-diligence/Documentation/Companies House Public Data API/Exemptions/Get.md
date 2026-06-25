Company exemptions information

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/exemptions
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number that the exemptions list is required for. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK Successful response | [companyExemptions](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/companyexemptions?v=latest) |
| 401 | Unauthorized Unauthorised |  |
| 404 | Not Found Resource not found |  |
