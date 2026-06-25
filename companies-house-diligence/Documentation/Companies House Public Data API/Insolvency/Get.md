Company insolvency information

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/insolvency
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number of the basic information to return. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK Company insolvency resource returned | [companyInsolvency](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/companyinsolvency?v=latest) |
| 401 | Unauthorized Unauthorized |  |
| 404 | Not Found Resource not found |  |
