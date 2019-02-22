import requests
from django.conf import settings
from django import forms
from dateutil.parser import parse
from crispy_forms.layout import Layout, Div

from tom_observations.facility import GenericObservationForm
from tom_observations.facility import GenericObservationFacility
from tom_targets.models import Target

from tom_observations.facilities import gemini

import logging

logger = logging.getLogger(__name__)

try:
    SNEX_GEMINI_SETTINGS = settings.FACILITIES['SNExGemini']
except KeyError:
    SNEX_GEMINI_SETTINGS = gemini.GEMINI_DEFAULT_SETTINGS

PORTAL_URL = SNEX_GEMINI_SETTINGS['portal_url']
TERMINAL_OBSERVING_STATES = gemini.TERMINAL_OBSERVING_STATES
SITES = gemini.SITES


def proposal_choices():
    return [(proposal, proposal) for proposal in SNEX_GEMINI_SETTINGS['programs']]


def obs_choices():
    choices = []
    for p in GEM_SETTINGS['programs']:
        for obs in GEM_SETTINGS['programs'][p]:
            obsid = p + '-' + obs
            val = p.split('-')
            showtext = val[0][1]+val[1][2:]+val[2]+val[3]+ ' - '+ GEM_SETTINGS['programs'][p][obs]
            choices.append((obsid,showtext))
    return choices


def get_site(progid,location=False):
    values = progid.split('-')
    gemloc = {'GS': 'Gemini South', 'GN': 'Gemini North'}
    site = values[0].upper()
    if location:
        site = gemloc[site]
    return site


def isodatetime(value):
    isostring = parse(value).isoformat()
    ii = isostring.find('T')
    date = isostring[0:ii]
    time = isostring[ii + 1:]
    return date, time


class SNExGeminiObservationForm(GenericObservationForm):

    telescope = forms.ChoiceField(choices=(('north', 'Gemini North'), ('south', 'Gemini South')))
    max_airmass = forms.FloatField(min_value=1.0, max_value=5.0, label='Airmass <', initial=2.0)
    window_size = forms.FloatField(label='Once in the next', initial=1.0)

    g_exptime = forms.FloatField(label='g', initial=0.0)
    r_exptime = forms.FloatField(label='r', initial=0.0)
    i_exptime = forms.FloatField(label='i', initial=0.0)
    z_exptime = forms.FloatField(label='z', initial=0.0)

    j_exptime = forms.FloatField(label='J', initial=0.0)
    h_exptime = forms.FloatField(label='H', initial=0.0)
    k_exptime = forms.FloatField(label='K', initial=0.0)

    gmos_grating = forms.ChoiceField(choices=(('B600', 'B600'), ('R400', 'R400')))
    gmos_exptime = forms.FloatField(initial=0.0)

    gnirs_exptime = forms.FloatField(initial=0.0)

    flamingos_grating = forms.ChoiceField(choices=(('JH', 'JH'), ('HK', 'HK')))
    flamingos_exptime = forms.FloatField(initial=0.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            self.common_layout,
            Div(
                Div(
                    'obsid', 'posangle', 'brightness', 'eltype', 'note', 'gstarg', 'gsbrightness',
                    css_class='col'
                ),
                Div(
                    'ready', 'pamode', 'brightness_band', 'elmin', 'window_start', 'gsra', 'gsbrightness_band',
                    css_class='col'
                ),
                Div(
                    'group', 'obsdate', 'brightness_system', 'elmax', 'window_duration', 'gsdec', 'gsbrightness_system',
                    css_class='col'
                ),
                css_class='form-row'
            ),
            Div(
                Div(
                    'inst', 'iq', 'overwrite',
                    css_class='col'
                ),
                Div(
                    'gsprobe', 'cc', 'port',
                    css_class='col'
                ),
                Div(
                    'ifu', 'sb',
                    css_class='col'
                ),
                css_class='form-row'
            )
        )

    def is_valid(self):
        super().is_valid()
        errors = SNExGemini.validate_observation(self.observation_payload)
        if errors:
            self.add_error(None, errors)
        return not errors

    @property
    def observation_payload(self):
        target = Target.objects.get(pk=self.cleaned_data['target_id'])

        ii = self.cleaned_data['obsid'].rfind('-')
        progid = self.cleaned_data['obsid'][0:ii]
        obsnum = self.cleaned_data['obsid'][ii+1:]
        payload = {
            "prog": progid,
            # "password": self.cleaned_data['userkey'],
            "password": SNEX_GEMINI_SETTINGS['api_key'][get_site(self.cleaned_data['obsid'])],
            # "email": self.cleaned_data['email'],
            "email": GEM_SETTINGS['user_email'],
            "obsnum": obsnum,
            "target": target.name,
            "ra": target.ra,
            "dec": target.dec,
            "note": self.cleaned_data['note'],
            "ready": True,
        }

        if self.cleaned_data['brightness'] != None:
            smags = str(self.cleaned_data['brightness']).strip() + '/' + \
                self.cleaned_data['brightness_band'] + '/' + \
                self.cleaned_data['brightness_system']
            payload["mags"] = smags

        if self.cleaned_data['group'].strip() != '':
            payload['group'] = self.cleaned_data['group'].strip()

        # timing window?
        if self.cleaned_data['window_start'].strip() != '':
            wdate, wtime = isodatetime(self.cleaned_data['window_start'])
            payload['windowDate'] = wdate
            payload['windowTime'] = wtime
            payload['windowDuration'] = str(self.cleaned_data['window_duration']).strip()

        # airmass
        payload['elevationType'] = 'airmass'
        payload['elevationMin'] = '1.0'
        payload['elevationMax'] = str(self.cleaned_data['max_airmass']).strip()

        return payload


class SNExGemini(GenericObservationFacility):
    name = 'Gemini'
    form = SNExGeminiObservationForm

    @classmethod
    def submit_observation(clz, observation_payload):
        response = requests.post(PORTAL_URL[get_site(observation_payload['prog'])] + '/too',
                                 verify=False, params=observation_payload)
        response.raise_for_status()
        # Return just observation number
        observation_id = response.text.split('-')
        return [observation_id[-1]]

    @classmethod
    def validate_observation(clz, observation_payload):
        return {}

    @classmethod
    def get_observation_url(clz, observation_id):
        return ''

    @classmethod
    def get_terminal_observing_states(clz):
        return TERMINAL_OBSERVING_STATES

    @classmethod
    def get_observing_sites(clz):
        return SITES

    @classmethod
    def get_observation_status(clz, observation_id):
        return ''

    @classmethod
    def data_products(clz, observation_record, product_id=None):
        return []
