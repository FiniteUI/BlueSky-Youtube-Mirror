from atproto import Client, models, exceptions, IdResolver, Session, SessionEvent
from bs4 import BeautifulSoup
import requests
from datetime import datetime
from PIL import Image
from io import BytesIO

class BlueSky:
    def __init__(self, username=None, password=None, session=None):
        self.client = Client()
        self.id_resolver = IdResolver()
        self.message_client = None

        self.username = username
        self.password = password
        self.session = session
        self.logged_in = False

    def login(self):
        try:
            if self.session is not None:
                self.client.login(session_string=self.session)
            else:
                self.client.login(self.username, self.password)
                self.session = self.client.export_session_string()

            print(f'Successful BlueSky login as user {self.username}')

            self.logged_in = True
            self.client.on_session_change(self.on_session_change)

            self.message_client = self.client.with_bsky_chat_proxy().chat.bsky.convo
        except (exceptions.UnauthorizedError, exceptions.BadRequestError) as e:
            print("Failed to authorize with BlueSky")
            print(e)

        return self.logged_in

    def on_session_change(self, event: SessionEvent, session: Session):
        print(f'Session Change for user {self.username}')
        if event in (SessionEvent.CREATE, SessionEvent.REFRESH):
            self.session = self.client.export_session_string()

    def post(self, contents, links: list = None, mentions: list = None, link_embed = None, hashtags: list = None, images: list[bytes] = None, images_alt_text: list = None):
        #handle links and mentions
        facets = None
        if links is not None or mentions is not None:
            facets = self.generate_facets(contents, links, mentions, hashtags)

        #images and embeds can't be posted together
        #images take precedence
        if not images:
            #handle embedded link (only one)
            if link_embed is not None:
                link_embed = self.get_link_embed_details(link_embed)

        if images:
            if not images_alt_text:
                images_alt_text = ['' for i in images]

            aspect_ratios = []
            for i in images:
                image = Image.open(BytesIO(i))
                ar = models.AppBskyEmbedDefs.AspectRatio(height=image.size[1], width=image.size[0])
                aspect_ratios.append(ar)

            if len(images) == 1:
                post = self.client.send_image(contents, image=images[0], image_alt=images_alt_text[0], image_aspect_ratio=aspect_ratios[0], facets=facets)
            else:
                post = self.client.send_images(contents, images=images, image_alts=images_alt_text, image_aspect_ratios=aspect_ratios, facets=facets)
        else:
            post = self.client.send_post(contents, facets=facets, embed=link_embed)

        return post.uri

    def get_link_embed_details(self, link):
        title = ''
        description = ''
        thumbnail = None

        response = requests.get(link)
        response.raise_for_status()
        data = BeautifulSoup(response.text, "html.parser")

        title_tag = data.find("meta", property="og:title")
        if title_tag:
            title = title_tag['content']

        description_tag = data.find("meta", property="og:description")
        if description_tag:
            description = description_tag["content"]
        
        image_tag = data.find("meta", property="og:image")
        if image_tag:
            img_url = image_tag["content"]
            if "://" not in img_url:
                img_url = link + img_url
            response = requests.get(img_url)
            response.raise_for_status()

            thumbnail = self.client.upload_blob(response.content).blob

        embed = models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                title=title,
                description=description,
                uri=link,
                thumb=thumbnail,
            )
        )
        
        return embed

    def generate_post_embed(uri, cid):
        embed = models.AppBskyEmbedRecord.Main(
            record = models.ComAtprotoRepoStrongRef.Main(cid=cid, uri=uri)
            )
        return embed

    def send_message(self, recipient, message, links: list=None, mentions: list=None, embed_post = None):
        print(f'Sending user [{recipient}] message [{message}]...')

        recipient_id = self.get_did_from_handle(recipient)
        if recipient_id is None:
            print(f"Error: Unable to find user [{recipient}]")
            return

        try:
            chat = self.message_client.get_convo_for_members(
                models.ChatBskyConvoGetConvoForMembers.Params(members=[recipient_id]),
            ).convo
        except exceptions.BadRequestError as e:
            print(f'Error: {e.response.content.message}. Message not sent.')
            return
            
        #handle links and mentions
        facets = None
        if links is not None or mentions is not None:
            facets = self.generate_facets(message, links, mentions)

        if embed_post is not None:
            embed = BlueSky.generate_post_embed(embed_post.uri, embed_post.cid)

        try:
            self.message_client.send_message(
                models.ChatBskyConvoSendMessage.Data(
                    convo_id=chat.id,
                    message=models.ChatBskyConvoDefs.MessageInput(
                        text=message,
                        facets=facets,
                        embed = embed
                    ),
                )
            )
        except exceptions.BadRequestError as e:
            print(f'Error: {e.response.content.message}. Message not sent.')

    def generate_facets(self, text: str, links: list=None, mentions: list=None, hashtags: list=None):
        #pass list of links and mentions
        #this function will parse those from the text and generate the rich text facet
        #only handles explicit links
        facets = []

        if links is not None:
            for l in links:
                start = text.encode().find(l.encode())
                if start != -1:
                    link = models.AppBskyRichtextFacet.Link(uri=l)
                    position = models.AppBskyRichtextFacet.ByteSlice(byte_start=start, byte_end=start + len(l))
                    facet = models.AppBskyRichtextFacet.Main(features=[link], index=position)
                    facets.append(facet)

        if mentions is not None:
            for m in mentions:
                mention_full = f'@{m}'
                start = text.encode().find(mention_full.encode())
                if start != -1:
                    mention_id = self.get_did_from_handle(m)
                    if mention_id is not None:
                        mention = models.AppBskyRichtextFacet.Mention(did=mention_id)
                        position = models.AppBskyRichtextFacet.ByteSlice(byte_start=start, byte_end=start + len(mention_full))
                        facet = models.AppBskyRichtextFacet.Main(features=[mention], index=position)
                        facets.append(facet)

        if hashtags is not None:
            for h in hashtags:
                start = text.encode().find(h.encode())
                if start != -1:
                    hashtag = models.AppBskyRichtextFacet.Tag(tag=h.replace('#', ''))
                    position = models.AppBskyRichtextFacet.ByteSlice(byte_start=start, byte_end=start + len(h))
                    facet = models.AppBskyRichtextFacet.Main(features=[hashtag], index=position)
                    facets.append(facet)

        if facets == []:
            facets = None

        return facets
    
    def get_did_from_handle(self, handle):
        return self.id_resolver.handle.resolve(handle)
    
    def get_handle_from_did(self, did):
        return self.id_resolver.did.resolve(did).also_known_as[0].replace('at://', '')

    def get_did(self):
        return self.get_did_from_handle(self.username)
    
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

    def build_post_url(author, key):
        return f'https://bsky.app/profile/{author}/post/{key}'
        
    def get_post_uri_details(uri):
        #get post key and user from uri
        uri_split = uri.split('/')
        did = uri_split[2]
        key = uri_split[4]

        return did, key

    def get_post_uri_from_url(self, url):
        url_split = url.split('/')
        rkey = url_split[len(url_split) - 1]
        handle = url_split[4]
        return self.client.get_post(rkey, handle).uri

    def get_profile(self, did):
        return self.client.app.bsky.actor.profile.get(did, 'self').value

    def update_profile(self, display_name=None, description=None, avatar=None, banner=None, pinned_post_uri=None):
        if display_name is None and description is None and avatar is None and banner is None and pinned_post_uri is None:
            return

        current_profile = self.get_profile(self.get_did())
        record = models.AppBskyActorProfile.Record(display_name=current_profile.display_name, description=current_profile.description, avatar=current_profile.avatar, banner=current_profile.banner, pinned_post=current_profile.pinned_post)

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

        self.client.com.atproto.repo.put_record(
            models.ComAtprotoRepoPutRecord.Data(
                repo=self.get_did(),
                record=record,
                rkey='self',
                collection=models.ids.AppBskyActorProfile
            )
        )

    def pin_post(self, uri):
        return self.update_profile(pinned_post_uri=uri)

if __name__ == "__main__":
    print('This module should not be run directly.')