from django import forms

from apps.ticket.models import Ticket


class TicketCreateForm(forms.Form):
    source_type = forms.ChoiceField(
        label="来源类型",
        choices=Ticket.SourceType.choices,
    )
    issue_type = forms.ChoiceField(
        label="问题类型",
        choices=[("", "---------")] + list(Ticket.IssueType.choices),
        required=False,
    )
    description = forms.CharField(
        label="问题描述",
        widget=forms.Textarea(attrs={"rows": 4}),
        required=True,
    )
