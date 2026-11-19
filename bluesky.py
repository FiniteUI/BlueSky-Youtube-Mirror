import asyncio
from datetime import UTC, datetime
from io import BytesIO

import favicon
import requests
from atproto import Client, IdResolver, Session, SessionEvent, exceptions, models
from atproto_client.models.utils import create_strong_ref
from bs4 import BeautifulSoup
from PIL import Image

from request_handler import RequestHandler

MAX_THUMBNAIL_SIZE = 1000000


class BlueSky:
    def __init__(self, username=None, password=None, session=None, did=None, oauth_client=None):
        self.username = username
        self.password = password
        self.did = did
        self.session = session
        self.oauth_client = oauth_client

        self.logged_in = False
        self.error = None
        self.handle = None
        self.message_client = None

        self.client = Client()
        self.id_resolver = IdResolver()

    def login(self):
        try:
            if self.oauth_client is not None:
                self.oauth_session = asyncio.run(self.oauth_client.session_store.get_session(self.did))
                if not self.oauth_session:
                    raise ValueError(f'No active OAuth session found for did {self.did}')
                self.active_oauth_session = asyncio.run(self.oauth_client.refresh_session(self.oauth_session))
            elif self.session is not None:
                self.client.login(session_string=self.session)
            else:
                if self.did is not None:
                    self.client.login(self.did, self.password)
                else:
                    self.client.login(self.username, self.password)
        except (
            exceptions.UnauthorizedError,
            exceptions.BadRequestError,
            exceptions.TimeoutError,
            ValueError,
        ) as e:
            self.error = 'Failed to authorize with BlueSky: ' + str(e)
            print(self.error)
            return False

        self.post_login()

        print(f'Successful BlueSky login as user {self.handle}')
        self.logged_in = True
        self.error = None

        return self.logged_in

    def post_login(self):
        if self.did is None:
            self.did = self.get_did()

        if self.handle is None:
            self.handle = self.get_handle_from_did(self.did)

        if self.oauth_client is None:
            self.session = self.client.export_session_string()
            self.client.on_session_change(self.on_session_change)

        self.message_client = self.client.with_bsky_chat_proxy().chat.bsky.convo

    def on_session_change(self, event: SessionEvent, session: Session):
        print(f'Session Change for user {self.handle}')
        if event in (SessionEvent.CREATE, SessionEvent.REFRESH):
            self.session = self.client.export_session_string()

    def post(
        self,
        contents,
        link_embed=None,
        images: list[bytes] | None = None,
        images_alt_text: list | None = None,
        embed_title=None,
        embed_description=None,
        embed_image_link=None,
        manual_links: list[tuple] | None = None
    ):
        uri = None

        # handle links and mentions
        facets = self.client.detect_facets(contents)

        # handle manual links
        # manual links should be a list of tuples (link_text, link_url)
        if manual_links:
            for link in manual_links:
                link_facet = self.generate_manual_link_facet_from_match(contents, link[0], link[1])
                if link_facet:
                    facets.append(link_facet)

        # images and embeds can't be posted together
        # images take precedence
        if not images:
            # handle embedded link (only one)
            if link_embed is not None:
                link_embed = self.get_link_embed_details(
                    link_embed,
                    embed_title=embed_title,
                    embed_description=embed_description,
                    embed_image_link=embed_image_link,
                )

        if images:
            if not images_alt_text:
                images_alt_text = ['' for i in images]

            aspect_ratios = []
            for i in images:
                image = Image.open(BytesIO(i))
                ar = models.AppBskyEmbedDefs.AspectRatio(height=image.size[1], width=image.size[0])
                aspect_ratios.append(ar)

            if len(images) == 1:
                post = self.client.send_image(
                    contents,
                    image=images[0],
                    image_alt=images_alt_text[0],
                    image_aspect_ratio=aspect_ratios[0],
                    facets=facets,
                )
            else:
                post = self.client.send_images(
                    contents,
                    images=images,
                    image_alts=images_alt_text,
                    image_aspect_ratios=aspect_ratios,
                    facets=facets,
                )
        else:
            if self.oauth_client is None:
                post = self.client.send_post(contents, facets=facets, embed=link_embed)
                uri = post.uri
            else:
                post = self.send_post_oauth(contents, facets, link_embed)
                uri = post['uri']

        return uri

    def send_post_oauth(self, contents, facets, embed):
        now = datetime.now(UTC).isoformat().replace('+00:00', 'Z')

        data = {'$type': 'app.bsky.feed.post', 'text': contents, 'createdAt': now}

        if facets:
            data['facets'] = [models.get_model_as_dict(f) for f in facets]

        if embed:
            data['embed'] = models.get_model_as_dict(embed)

        url = f'{self.active_oauth_session.pds_url.rstrip("/")}/xrpc/com.atproto.repo.createRecord'
        body = {'repo': self.did, 'collection': 'app.bsky.feed.post', 'record': data}

        print(f'POST - [{url}]')
        response = asyncio.run(self.oauth_client.make_authenticated_request(session=self.active_oauth_session, method='POST', url=url, json=body))
        print(response)
        response.raise_for_status()

        return response.json()

    def get_link_embed_details(
        self,
        link,
        embed_title=None,
        embed_description=None,
        embed_image_link=None,
    ):
        print(f'Generating embed for link [{link}]...')
        title = ''
        description = ''
        thumbnail = None
        img_url = None

        if embed_title and embed_description and embed_image_link:
            title = embed_title
            description = embed_description
            img_url = embed_image_link
        else:
            print(f'GET - [{link}]')
            with RequestHandler() as request:
                response = request.get(link)

            print(response)
            response.raise_for_status()
            text = response.text

            data = BeautifulSoup(text, 'html.parser')

            title_tag = data.find('meta', property='og:title')
            if title_tag:
                title = title_tag['content']

            description_tag = data.find('meta', property='og:description')
            if description_tag:
                description = description_tag['content']

            image_tag = data.find('meta', property='og:image')
            if image_tag:
                img_url = image_tag['content']
                if '://' not in img_url:
                    img_url = link + img_url

        if img_url:
            print(f'GET - [{img_url}]')
            with RequestHandler() as request:
                response = request.get(img_url)

            print(response)
            response.raise_for_status()

            thumbnail = BlueSky.compress_embed_thumbnail(response.content)
            if self.oauth_client is None:
                thumbnail = self.client.upload_blob(thumbnail).blob
            else:
                thumbnail = self.upload_blob_oauth(thumbnail)

        else:
            print('Unable to generate embed thumbnail.')

        embed = models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                title=title,
                description=description,
                uri=link,
                thumb=thumbnail,
            )
        )

        return embed

    def upload_blob_oauth(self, data, content_type='image/jpeg'):
        # manually upload blob since python sdk doesn't support oauth yet
        url = f'{self.active_oauth_session.pds_url.rstrip("/")}/xrpc/com.atproto.repo.uploadBlob'

        print(f'POST - [{url}]')
        response = asyncio.run(
            self.oauth_client.make_authenticated_request(
                session=self.active_oauth_session,
                method='POST',
                url=url,
                content=data,
                headers={'Content-Type': content_type, 'Content-Length': str(len(data))},
            )
        )
        print(response)
        response.raise_for_status()

        return response.json()['blob']

    def send_message(
        self,
        recipient,
        message,
        embed_post=None,
    ):
        print(f'Sending user [{recipient}] message [{message}]...')

        if recipient.startswith('did:'):
            recipient_id = recipient
        else:
            recipient_id = self.get_did_from_handle(recipient)

        if recipient_id is None:
            print(f'Error: Unable to find user [{recipient}]')
            return

        try:
            chat = self.message_client.get_convo_for_members(
                models.ChatBskyConvoGetConvoForMembers.Params(members=[recipient_id]),
            ).convo
        except exceptions.BadRequestError as e:
            print(f'Error: {e.response.content.message}. Message not sent.')
            return

        # handle links and mentions
        facets = self.client.detect_facets(message)

        embed = None
        if embed_post is not None:
            embed = BlueSky.generate_post_embed(embed_post.uri, embed_post.cid)

        try:
            self.message_client.send_message(
                models.ChatBskyConvoSendMessage.Data(
                    convo_id=chat.id,
                    message=models.ChatBskyConvoDefs.MessageInput(text=message, facets=facets, embed=embed),
                )
            )
        except exceptions.BadRequestError as e:
            print(f'Error: {e.response.content.message}. Message not sent.')

    def get_did_from_handle(self, handle):
        return self.id_resolver.handle.resolve(handle)

    def get_handle_from_did(self, did):
        return self.id_resolver.did.resolve(did).also_known_as[0].replace('at://', '')

    def get_did(self):
        return self.client.me.did

    def get_mentions(self, limit=100, cutoff_timestamp=None):
        params = models.AppBskyNotificationListNotifications.ParamsDict(limit=limit, reasons=['mention'])
        mentions = self.client.app.bsky.notification.list_notifications(params).notifications

        if cutoff_timestamp:
            for i in range(len(mentions) - 1, -1, -1):
                indexed_at = datetime.fromisoformat(mentions[i].indexed_at)
                if indexed_at < cutoff_timestamp:
                    mentions.pop(i)

        return mentions

    def get_post_from_uri(self, uri):
        did, key = BlueSky.get_post_uri_details(uri)
        post = self.client.get_post(key, did)

        return post

    def get_parent_post_from_reply(self, reply):
        return self.get_post_from_uri(reply.reply.parent.uri)

    def get_post_url_from_post(self, post):
        did, key = BlueSky.get_post_uri_details(post.uri)
        handle = self.get_handle_from_did(did)
        url = BlueSky.build_post_url(handle, key)

        return url

    def get_post_uri_from_url(self, url):
        url_split = url.split('/')
        rkey = url_split[len(url_split) - 1]
        handle = url_split[4]
        return self.client.get_post(rkey, handle).uri

    def get_post_url_from_uri(self, uri):
        post = self.get_post_from_uri(uri)
        return self.get_post_url_from_post(post)

    def get_profile(self, did):
        return self.client.app.bsky.actor.profile.get(did, 'self').value

    def update_profile(self, display_name=None, description=None, avatar=None, banner=None, pinned_post_uri=None, links: list | None = None):
        if display_name is None and description is None and avatar is None and banner is None and pinned_post_uri is None and links is None:
            return

        current_profile = self.get_profile(self.get_did())
        record = models.AppBskyActorProfile.Record(
            display_name=current_profile.display_name,
            description=current_profile.description,
            avatar=current_profile.avatar,
            banner=current_profile.banner,
            pinned_post=current_profile.pinned_post,
            links=current_profile.links,
        )

        if display_name:
            record.display_name = display_name
        if description:
            record.description = description
        if avatar:
            record.avatar = self.client.upload_blob(avatar).blob
        if banner:
            record.banner = self.client.upload_blob(banner).blob
        if pinned_post_uri:
            record.pinned_post = self.get_post_from_uri(pinned_post_uri)
        if links:
            record.links = self.generate_profile_link_records(links)

        self.client.com.atproto.repo.put_record(
            models.ComAtprotoRepoPutRecord.Data(
                repo=self.get_did(),
                record=record,
                rkey='self',
                collection=models.ids.AppBskyActorProfile,
            )
        )

    def generate_profile_link_records(self, links: list):
        # generate profile link records from a list of links
        # links should be a list of tuples (url, title)

        existing_links = self.get_profile_links()

        final_links = []
        for link in links:
            # check if link already exists
            existing_link = None
            for l in existing_links:
                if link[0].lower().removesuffix('/') == l.value.url.lower().removesuffix('/') and link[1].lower() == l.value.title.lower():
                    existing_link = l
                    break

            if existing_link:
                final_links.append(existing_link)
                continue

            # create the link record
            icon = self.get_link_icon(link[0])
            link_record = models.AppBskyActorLink.Record(created_at=datetime.now(UTC).isoformat(), url=link[0], title=link[1], icon=icon)

            link_record = self.client.com.atproto.repo.create_record(
                models.ComAtprotoRepoCreateRecord.Data(repo=self.get_did(), collection='app.bsky.actor.link', record=link_record)
            )
            strong_ref = create_strong_ref(link_record)
            final_links.append(strong_ref)

        return final_links

    def get_profile_links(self):
        profile = self.get_profile(self.get_did())
        links = []

        if profile.links:
            for l in profile.links:
                link_record = self.client.com.atproto.repo.get_record(
                    models.ComAtprotoRepoGetRecord.Params(repo=self.get_did(), collection='app.bsky.actor.link', rkey=l.uri.split('/')[-1])
                )
                links.append(link_record)

        return links

    def get_link_icon(self, url):
        # grab icon link
        icon = favicon.get(url)
        if not icon:
            print(f'Failed to retreive icon for link: {url}')
            return None

        # now grab actual image
        icon = icon[0].url
        print(f'GET - [{icon}]')
        response = requests.get(icon)
        print(response)
        response.raise_for_status()

        image = BlueSky.convert_icon_to_png(response.content)
        if self.oauth_client is None:
            icon_blob = self.client.upload_blob(image).blob
        else:
            icon_blob = self.upload_blob_oauth(image)

        return icon_blob

    def pin_post(self, uri):
            return self.update_profile(pinned_post_uri=uri)

    def go_live(self, live_link, duration_minutes):
        # generate embed
        embed = self.get_link_embed_details(live_link)

        #generate live status record
        live_status = models.AppBskyActorStatus.Record(
            status='app.bsky.actor.status#live',
            created_at=datetime.now(UTC).isoformat(),
            duration_minutes=duration_minutes,
            embed=embed
        )

        # upload record
        self.client.com.atproto.repo.put_record(
            models.ComAtprotoRepoPutRecord.Data(
                repo=self.did,
                collection='app.bsky.actor.status',
                rkey='self',
                record=live_status,
            )
        )

    def end_live(self):
        # delete status record
        self.client.com.atproto.repo.delete_record(
            models.ComAtprotoRepoDeleteRecord.Data(
                repo=self.did,
                collection='app.bsky.actor.status',
                rkey='self',
            )
        )

    @staticmethod
    def convert_icon_to_png(bytes):
        image = Image.open(BytesIO(bytes))
        output = BytesIO()

        image.save(output, format='PNG')

        return output.getvalue()

    @staticmethod
    def compress_embed_thumbnail(thumbnail: bytes):
        if len(thumbnail) <= MAX_THUMBNAIL_SIZE:
            return thumbnail

        quality = MAX_THUMBNAIL_SIZE / len(thumbnail)
        quality = round(quality * 95, 0)
        print(f'Compressing image to {quality}% quality...')

        image = Image.open(BytesIO(thumbnail))
        image = image.save(image, quality)

        return image.getvalue()

    @staticmethod
    def build_post_url(author, key):
            return f'https://bsky.app/profile/{author}/post/{key}'

    @staticmethod
    def get_post_uri_details(uri):
        # get post key and user from uri
        uri_split = uri.split('/')
        did = uri_split[2]
        key = uri_split[4]

        return did, key

    @staticmethod
    def generate_post_embed(uri, cid):
        embed = models.AppBskyEmbedRecord.Main(record=models.ComAtprotoRepoStrongRef.Main(cid=cid, uri=uri))
        return embed

    @staticmethod
    def generate_manual_link_facet_from_match(full_text, link_text, link_url):
        full_text_encoded = full_text.encode()
        link_text_encoded = link_text.encode()

        facet = None
        start = full_text_encoded.find(link_text_encoded)
        if start != -1:
            link = models.AppBskyRichtextFacet.Link(uri=link_url)
            position = models.AppBskyRichtextFacet.ByteSlice(byte_start = start, byte_end = start + len(link_text_encoded))
            facet = models.AppBskyRichtextFacet.Main(features=[link], index=position)

        return facet

if __name__ == '__main__':
    print('This module should not be run directly.')
