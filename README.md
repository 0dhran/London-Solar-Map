# London-Solar-Map
Firstly, I want to clarify that this work is currently in draft form. I am building on work, products and data from many sources and I want to ensure that they are fully cited and their terms of use are not breached. So far the work relies on: the London Solar Opportunity Map (GLA and UCL); OS Open TOID Locations (Ordnance Survey); Satelite imagery (ESRI); INSPIRE and CCOD/OCOD records (HM Land Registry).

Tool to identify potential Community Solar sites in Southwark, and potentially more broadly (London, the UK). 

## Motivation
At Southwark Community Energy our solar site pipeline is currently mostly stalled due to the Department of Education blocking new solar sites while they investigate a standard approach for all schools https://communityenergyengland.org/news/community-energy-englands-response-to-dfe-announcement/ .

Our other site identification avenue is through Southwark Council owned buildings, I'm under the impression that the council is currently doing a site inventory to check feasibility for all of their sites (double-check with Rachel K).

So far, site identification is done through recommendations from outreach (e.g. someone knows a school that would be keen, or a social housing block with a suitable roof) or through a map-based site search. Obviously we will keep up the outreach and recommendation, as sites from this route have been 'pre-approved' (stakeholders are keen, the roof is good etc.). But we can improve our map-based search process.

This was the informal map-search process initially:
- Check the London Solar Opportunity Map (LSOM) to identify buildings where the solar potential is significantly high. https://apps.london.gov.uk/lsom/
  - Potentially double-checking on Solar Wizard https://solarwizard.org.uk/wizard
- Inspect potential sites on Google Earth (satellite imagery) to see if the roof is sufficiently clear of clutter to have solar PVs installed.
- Check the Land Registry to see who owns the potential site / is it a registered building.
  - Can also use We used this before: https://landexplorer.coop/ and https://www.carbon.place/landownership/#/landowners/#8/51.482/-0.151/0/0/greyscale_nobuild
 
My two problems with this approach were that it was inefficient and not formalised, meaning there must be a huge amount of duplication of work from people searching over the same area many times. I now suspect that not many solar sites are found through map search in the first place, but are mostly from looking at pre-approved lists (schools, social housing etc.). However, we will eventually exhaust these sites (I imagine?), and so a tool that can identify suitable sites or groups of sites at mass builds up an argument and a business case that can be used to leverage policy and premises owners. This should be possible to do through machine vision and other automation approaches, but we don't have the resources (work hours, money to pay for data and processing power) to do this right now.

For now, I want to formalise the process as is so we can start to see what information we need to effectively identify sites by map, to inform the future automated approach. When the process was demoed to me, it  took some time to identify the building on Google Earth from LSOM. It seems reasonable that a tool that links different databases (satellite, solar opportunity, ownership info) would streamline the process, allowing for filtering by different metrics (e.g. only schools, roof size > 300m^2 etc), as well as co-ordinating where has previously been searched. Ideally, the tool would also be open source and transferable not only to the rest of London, but across the UK/England. 

## Where we are now
New process:
We have an interactive dashboard hosted on Render at https://southwark-solar-roofspotting.onrender.com/ . The dashboard includes a satellite map that allows users to click on a building and see its solar data. The user is then directed to manually check other sites (solar wizard and land explorer) to record supplementary information, as well as to indicate if they think it is a suitable site, needs further review etc.

Structure:
We start with data from the London Solar Opportunity Map. I downloaded the dataset which for each building (identified by its TOID reference) in London records the total solar potential (estimated annual output kWh for the roof, based on a utilisation factor of 100%, the LSOM uses a 11.9% factor in its own dashboard) and the viable roof space (tilt less than 65 deg and annual potential sufficiently high per m^2). This data has not been updated since 2019, means new builds/renovations are inaccurate, not sure of the size of this issue.

This solar and roof data is geolocated using the OS Open TOID map i.e. the OS map joins the buildings and their location using the TOID column. We do not have access to the building shape, as this is behind the OS Master Map paywall (we can access it through an end-user license agreement from Southwark Council, Public Service Geospatial Agreement (PSGA) member - Is there much of an advantage to this? would we still be able to let the map be open source in this case?).

Buildings, and their solar information, are represented as points that are overlayed on a satellite map of Southwark (during processing we bound the OS map so it just contains a box around Southwark, we then inner join this with the LSOM TOIDs, meaning we work with a much smaller dataset). In this version, I have filtered to only include buildings with viable roof size greater than 300m^2 (using LSOM roof variable) as this is the Repowering London recommendation. I also filtered to sites with annual solar potential below an arbitrary amount, to make more viable sites clearer and reduce computational load when refreshing. The points representing the buildings vary by size and colour: Red points have more solar potential, yellow have less; bigger points have more roof space, smaller have less.

The user so can click on a point, its information comes up on the side panel, they do the necessary review steps and input the figures then assign the site to a category e.g. Potentially suitable, requires investigation, not suitable etc. The user is expected to record the street address, search solar wizard to get a solar peak figure (standard for applications), and Land Explorer to get ownership information and adjudge if its a suitable site. This review is saved to a PostgreSQL database hosted for free on NEON. Lists of each category (potentially suitable etc.) can be exported from NEON and sent to the necessary contact at Repowering who will begin engaging the site. 

## Limitations
- Render can support multiple people reviewing at once. However, currently multiple reviews can be issued for each site.
- It is slow to load and can be slow to move from one site to the next, especially after saving a review.
- It doesn't look very appealing.
- There is a lot of manual work involved.
- I'm unsure on the use of certain tools in this context - can we use OS and Land Registry data like this?
- Solar wizard is difficult to find the address for certain buildings - you can upgrade to premium to see a map I believe.

Potential expansions:
- Abandon LSOM for OpenStreetMap or similar (buildings) to avoid Ordnance Survey copyright issues with making open source. Requires creating our own model of solar opportunity.

## Appendices
### Data Sources
https://osdatahub.os.uk/data/downloads/open/OpenTOID for the OS map

https://data.london.gov.uk/dataset/london-solar-opportunity-map-lsom-vdxyl for the LSOM data

### A note on Solar Output
We want Solar peak output (kWp), which is the maximum power output of a solar project. How do we adjudge this? They currently use solar wizard.

May be a way to translate from LSOM.

Would be good to just get a classification algorithm to look at a roof and do this for us rather than relying on old LSOM data.

### Framing as an academic paper : 
MAy be meeting with Chris Grundy of LSHTM. Not sure the best way to do this, like it can be purely technical, or could be more about the impact of the tool on process in CES (in a public health way?). Maybe try frame it as 'can the use of machine learning have a positive public health effect?' 

I reckon a case-study, just documenting how effective it's been - probably mentioning changes in effectiveness, and maybe going into other things. Perplexity recommended formally testing if the search quality decreased which seems overkill right now since we're not operating at full capacity. 

## To-Do



### Question List
[**Q** Can we get Smart Meter data to identify places with high daily electricity use that may map up well with solar profiles.]
