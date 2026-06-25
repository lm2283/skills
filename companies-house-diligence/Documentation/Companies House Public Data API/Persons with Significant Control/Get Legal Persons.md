# Get the legal person with significant control notification

Get details of the legal person with significant control notification

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/persons-with-significant-control/legal-person/{notification_id}
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number of the legal person with significant control details being requested. | Required |
| notification_id | string | The notification id of the legal person with significant control notification being requested. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK LegalPersonPSC resource returned | [legalPerson](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/legalperson?v=latest) |
| 401 | Unauthorized Unauthorised |  |
| 404 | Not Found Resource not found |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
