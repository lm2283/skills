# Company profile

Get the basic company information

## Request

```
GET https://api.company-information.service.gov.uk/company/{companyNumber}
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
| 200 | OK readCompanyProfile | [companyProfile](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/companyprofile?v=latest) |
| 401 | Unauthorized Unauthorised |  |
| 404 | Not Found Resource not found |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
