# Persons with significant control Notification List

List of all notifications of a specific person with significant control

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/persons-with-significant-control/{psc_id}/notifications
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| psc_id | string | The person with significant control id of the notification list being requested | Required |

## Query parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| filter | string | Use “active” to return only active notifications. |  |
| items_per_page | integer | The number of notifications to return per page. |  |
| start_index | integer | The first row of data to retrieve, starting at 0. Use this parameter as a pagination mechanism along with the items_per_page parameter. |  |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK List the person with significant control notifications | [notificationList](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/notificationlist?v=latest) |
| 400 | Bad Request Bad request |  |
| 401 | Unauthorized Unauthorised |  |
