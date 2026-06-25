# Officer Appointment List

List of all officer appointments

## Request

```
GET https://api.company-information.service.gov.uk/officers/{officer_id}/appointments
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| officer_id | string | The officer id of the appointment list being requested. | Required |

## Query parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| filter | string | Use “active” to return only active appointments. |  |
| items_per_page | integer | The number of appointments to return per page. |  |
| start_index | integer | The first row of data to retrieve, starting at 0. Use this parameter as a pagination mechanism along with the items_per_page parameter. |  |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK List the officer appointments | [appointmentList](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/appointmentlist?v=latest) |
| 400 | Bad Request Bad request |  |
| 401 | Unauthorized Unauthorised |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
