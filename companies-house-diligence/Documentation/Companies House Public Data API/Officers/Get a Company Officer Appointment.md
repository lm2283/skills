# Get a company officer appointment

Get details of an individual company officer appointment

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/appointments/{appointment_id}
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number of the officer list being requested. | Required |
| appointment_id | string | The appointment id of the company officer appointment being requested. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK Get a company officer appointment | [officerSummary](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/officersummary?v=latest) |
| 400 | Bad Request Bad request | [error](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/error?v=latest) |
| 401 | Unauthorized Unauthorised |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
