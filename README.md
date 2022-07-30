# incident-radiation

Calculate the incident radiation on geometry.

Such studies of incident radiation can be used to approximate the energy that can
be collected from photovoltaic or solar thermal systems. They are also useful
for evaluating the impact of a building's orientation on both energy use and the
size/cost of cooling systems. For studies of photovoltaic potential or building
energy use impact, a sky matrix from EPW radiation should be used. For studies
of cooling system size/cost, a sky matrix derived from the STAT file's clear sky
radiation should be used.

NOTE THAT REFLECTIONS OF SOLAR ENERGY ARE NOT INCLUDED IN THE ANALYSIS
PERFORMED BY THIS APP.

Ground reflected irradiance is crudely accounted for by means of an emissive
"ground hemisphere," which is like the sky dome hemisphere and is derived from
the ground reflectance that is associated with the connected _sky_mtx. This
means that including geometry that represents the ground surface will effectively
block such crude ground reflection.

## Quickstart

Install dependencies:

```console
> pip install -r app/requirements.txt
```

Start Streamlit

```console
> streamlit run app/app.py

  You can now view your Streamlit app in your browser.

  Network URL: http://172.17.0.2:8501
  External URL: http://152.37.119.122:8501

```

Make changes to your app in the `app.py` file inside the "app" folder.

## Run inside Docker image locally (Optional)

You can run the app locally inside Docker to ensure the app will work fine after the deployment.

You need to install Docker on your machine in order to be able to run this command

```console
> pollination-apps run app  --name "incident-radiation"
```

## Deploy to Pollination

```console
> pollination-apps deploy app --name "incident-radiation" --public --api-token "Your api token from Pollination"
```

## Configure Github Actions

In order to configure github actions to deploy your app you will need to:

1. [Create](https://docs.github.com/en/get-started/quickstart/create-a-repo) a repository on Github
2. [Rename](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository) the repository's main branch to "master"
3. [Add](https://docs.github.com/en/actions/security-guides/encrypted-secrets) a secret called `POLLINATION_TOKEN` with your Pollination API key as the value
4. Create [the first release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository) of your app on Github with the tag v0.0.0
5. In all your commit messages, use one of the following commit types;

   - `feat`: A new feature
   - `fix`: A bug fix
   - `docs`: Documentation only changes
   - `style`: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
   - `refactor`: A code change that neither fixes a bug nor adds a feature
   - `perf`: A code change that improves performance or size
   - `test`: Adding missing tests or correcting existing tests
   - `chore`: Other changes that don't modify src/test/
   - `build`: Changes that affect the build system or external dependencies (example: changing the version of a dependency)
   - `ci`: Changes to our CI or CD pipelines

   Examples of commit messages:

   - fix: Remove unused imports
   - feat: Add capability to use analysis period

   **Note** that the commit messages with only `fix` and `feat` type will trigger a deployment to Pollination.

Github actions will then package and deploy your code to an app called [incident-radiation](https://app.pollination.cloud//applications/incident-radiation)
