# Get natural officers disqualifications

Get a natural officer's disqualifications

## Request

```
GET https://api.company-information.service.gov.uk/disqualified-officers/natural/{officer_id}
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| officer_id | string | The disqualified officer's id. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK Natural officer's disqualifications returned | [naturalDisqualification](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/naturaldisqualification?v=latest) |
| 401 | Unauthorized Unauthorised |  |
| 404 | Not Found Resource not found |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
