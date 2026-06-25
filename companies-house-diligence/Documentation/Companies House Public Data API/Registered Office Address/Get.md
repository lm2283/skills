# Registered Office Address

Get the current address of a company

## Request

```
GET https://api.company-information.service.gov.uk/company/{companyNumber}/registered-office-address
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | Company number for registered office address | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK Successful response | [registeredOfficeAddress](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/registeredofficeaddress?v=latest) |
| 401 | Unauthorized Not authorised |  |
| 404 | Not Found Resource not found |  |
