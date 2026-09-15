# BlueSky YouTube Mirror
[![Docker Hub](https://img.shields.io/static/v1.svg?color=086dd7&labelColor=555555&logoColor=ffffff&label=&message=docker%20hub&logo=Docker)](https://hub.docker.com/repository/docker/finiteui/bluesky-youtube-mirror)

This is a tool for mirroring a YouTube channel to a BlueSky account. Once deployed, the tool will update the BlueSky profile profile picture, banner, display name, and description to match the YouTube channel. It will also make posts when any videos, shorts, or community posts are made by the YouTube channel.

> [!CAUTION]
> This project should NOT be used for impersonating YouTube channels. During initialization, it will create a pinned post giving credit to the original YouTube channel.

For an example of this project up and running see [this BlueSky Account](https://bsky.app/profile/banger-tv-mirror.finiteui.com) that mirror's the [BangerTV youtube channel](https://www.youtube.com/@bangertv).
<p align="center">
  <img width="606" height="390" alt="image" src="https://github.com/user-attachments/assets/d91aa56e-3f75-4f0f-89b8-8267c7929df1" />
  <img width="583" height="468" alt="image" src="https://github.com/user-attachments/assets/005175ba-e55f-4c19-83f7-702a64ae29f2" />
</p>

## Deployment
### Environment Variables
The project relies on an .env file for the credentials. See [.env.example](/.env.example) for an example. The fields required are as follows:
- **YOUTUBE_API_KEY** = API Key for accessing the YouTube API.
  - An API key can be created in the Google Developer Console: https://developers.google.com/youtube/v3/getting-started
- **CHANNEL_ID** = The YouTube channel ID.
  - This can be found on the channel home page by expanding the channel description, scrolling down to "Share Channel" and selecting "Copy Channel ID"
- **BLUESKY_ACCOUNT** = The BlueSky account for the bot
- **BLUESKY_APP_PASSWORD** = App password for the BlueSky account.
  - App passwords can be generated here: https://bsky.app/settings/app-passwords
- **ACCOUNT_OWNER** = BlueSky account for the bot owner.
  - This is used for attribution in the pinned post.

See the full environment variable list in [.env.example](/.env.example).

### Running the Project
#### Docker
The [docker](docker) folder contains two compose files.
- [docker-compose.yml](docker/docker-compose.yml) is for deploying from the DockerHub image.
- [source-compose.yml](docker/source-compose.yml) is for building the image and deploying from source.

Define the enviroment variables in an env file and make sure the path is correct in the env_file node of the docker compose file, then run compose.

In the project root, run
```powershell
docker compose -f docker/docker-compose.yml up --build -d
```
to deploy from DockerHub or
```powershell
docker compose -f docker/source-compose.yml up --build -d
```
to build from source.

#### Direct


 
 To run the project directly, first create a virtual environment and install the requirements, then run the project:
 ```powershell
python -m venv .venv
.venv/Scripts/Activate
pip install -r requirements.txt
python bluesky-youtube-mirror.py
```
  
