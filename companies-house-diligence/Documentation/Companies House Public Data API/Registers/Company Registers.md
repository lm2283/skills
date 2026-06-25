# Company registers

Get the company registers information

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/registers
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number of the register information to return. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK readCompanyRegister | [companyRegister](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/companyregister?v=latest) |
| 401 | Unauthorized Unauthorised |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
