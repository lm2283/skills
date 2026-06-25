# Company UK Establishments

List of uk-establishments companies

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/uk-establishments
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | Company number | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK Resource returned | [companyUKEstablishments](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/companyukestablishments?v=latest) |
| 401 | Unauthorized Unauthorised |  |
