import base64
import json
import logging
import os
import sys
from zipfile import ZipFile

# Add lambda Third party reqs to python path
sys.path.insert(0, os.path.abspath("__python_reqs__"))

from isatools import isatab
from isatools.model import (
    Investigation,
    Study,
    Assay,
    Process,
    Material,
    DataFile,
    OntologyAnnotation,
    plink,
    Protocol,
    Source,
    Sample,
    OntologySource,
    Characteristic,
    batch_create_materials,
    Publication,
    Person,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def create_isatools_zip(isatab_filename):
    create_descriptor()
    with open("/tmp/i_investigation.txt") as f:
        create_isatab_archive(f, target_filename=f"/tmp/{isatab_filename}.zip")

    with open(f"/tmp/{isatab_filename}.zip", "rb") as z:
        return base64.b64encode(z.read())


def create_response(isatab_filename, status_code=200):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/zip",
            "Content-Encoding": "zip",
            "Content-Disposition": f'attachment; filename="{isatab_filename}.zip"',
        },
        "body": create_isatools_zip(isatab_filename).decode("ascii"),
        "isBase64Encoded": True,
    }


def post_handler(event, context):
    logger.info(f"Event: {event}")
    # logger.info(f"Context: {vars(context)}")

    isatab_filename = "ISATab"
    body = event.get("body")

    if body is not None:
        isatab_filename = json.loads(body).get("isatab_filename")

    # TODO: error handling

    return create_response(isatab_filename)


def create_descriptor():
    """Returns a simple but complete ISA-Tab 1.0 descriptor for illustration."""

    # Create an empty Investigation object and set some values to the instance variables.

    investigation = Investigation()
    investigation.identifier = "i1"
    investigation.title = "My Simple ISA Investigation"
    investigation.description = (
        "We could alternatively use the class constructor's parameters to set some default "
        "values at the time of creation, however we want to demonstrate how to use the "
        "object's instance variables to set values."
    )
    investigation.submission_date = "2016-11-03"
    investigation.public_release_date = "2016-11-03"

    # Create an empty Study object and set some values. The Study must have a filename, otherwise when we serialize it
    # to ISA-Tab we would not know where to write it. We must also attach the study to the investigation by adding it
    # to the 'investigation' object's list of studies.

    study = Study(filename="s_study.txt")
    study.identifier = "s1"
    study.title = "My ISA Study"
    study.description = (
        "Like with the Investigation, we could use the class constructor to set some default values, "
        "but have chosen to demonstrate in this example the use of instance variables to set initial "
        "values."
    )
    study.submission_date = "2016-11-03"
    study.public_release_date = "2016-11-03"
    investigation.studies.append(study)

    # Some instance variables are typed with different objects and lists of objects. For example, a Study can have a
    # list of design descriptors. A design descriptor is an Ontology Annotation describing the kind of study at hand.
    # Ontology Annotations should typically reference an Ontology Source. We demonstrate a mix of using the class
    # constructors and setting values with instance variables. Note that the OntologyAnnotation object
    # 'intervention_design' links its 'term_source' directly to the 'obi' object instance. To ensure the OntologySource
    # is encapsulated in the descriptor, it is added to a list of 'ontology_source_references' in the Investigation
    # object. The 'intervention_design' object is then added to the list of 'design_descriptors' held by the Study
    # object.

    obi = OntologySource(
        name="OBI", description="Ontology for Biomedical Investigations"
    )
    investigation.ontology_source_references.append(obi)
    intervention_design = OntologyAnnotation(term_source=obi)
    intervention_design.term = "intervention design"
    intervention_design.term_accession = "http://purl.obolibrary.org/obo/OBI_0000115"
    study.design_descriptors.append(intervention_design)

    # Other instance variables common to both Investigation and Study objects include 'contacts' and 'publications',
    # each with lists of corresponding Person and Publication objects.

    contact = Person(
        first_name="Alice",
        last_name="Robertson",
        affiliation="University of Life",
        roles=[OntologyAnnotation(term="submitter")],
    )
    study.contacts.append(contact)
    publication = Publication(
        title="Experiments with Elephants", author_list="A. Robertson, B. Robertson"
    )
    publication.pubmed_id = "12345678"
    publication.status = OntologyAnnotation(term="published")
    study.publications.append(publication)

    # To create the study graph that corresponds to the contents of the study table file (the s_*.txt file), we need
    # to create a process sequence. To do this we use the Process class and attach it to the Study object's
    # 'process_sequence' list instance variable. Each process must be linked with a Protocol object that is attached to
    # a Study object's 'protocols' list instance variable. The sample collection Process object usually has as input
    # a Source material and as output a Sample material.

    # Here we create one Source material object and attach it to our study.

    source = Source(name="source_material")
    study.sources.append(source)

    # Then we create three Sample objects, with organism as Homo Sapiens, and attach them to the study. We use the utility function
    # batch_create_material() to clone a prototype material object. The function automatically appends
    # an index to the material name. In this case, three samples will be created, with the names
    # 'sample_material-0', 'sample_material-1' and 'sample_material-2'.

    prototype_sample = Sample(name="sample_material", derives_from=[source])
    ncbitaxon = OntologySource(name="NCBITaxon", description="NCBI Taxonomy")
    characteristic_organism = Characteristic(
        category=OntologyAnnotation(term="Organism"),
        value=OntologyAnnotation(
            term="Homo Sapiens",
            term_source=ncbitaxon,
            term_accession="http://purl.bioontology.org/ontology/NCBITAXON/9606",
        ),
    )
    prototype_sample.characteristics.append(characteristic_organism)

    study.samples = batch_create_materials(
        prototype_sample, n=3
    )  # creates a batch of 3 samples

    # Now we create a single Protocol object that represents our sample collection protocol, and attach it to the
    # study object. Protocols must be declared before we describe Processes, as a processing event of some sort
    # must execute some defined protocol. In the case of the class model, Protocols should therefore be declared
    # before Processes in order for the Process to be linked to one.

    sample_collection_protocol = Protocol(
        name="sample collection",
        protocol_type=OntologyAnnotation(term="sample collection"),
    )
    study.protocols.append(sample_collection_protocol)
    sample_collection_process = Process(executes_protocol=sample_collection_protocol)

    # Next, we link our materials to the Process. In this particular case, we are describing a sample collection
    # process that takes one source material, and produces three different samples.
    #
    # (source_material)->(sample collection)->[(sample_material-0), (sample_material-1), (sample_material-2)]

    for src in study.sources:
        sample_collection_process.inputs.append(src)
    for sam in study.samples:
        sample_collection_process.outputs.append(sam)

    # Finally, attach the finished Process object to the study process_sequence. This can be done many times to
    # describe multiple sample collection events.

    study.process_sequence.append(sample_collection_process)

    # Next, we build n Assay object and attach two protocols, extraction and sequencing.

    assay = Assay(filename="a_assay.txt")
    extraction_protocol = Protocol(
        name="extraction", protocol_type=OntologyAnnotation(term="material extraction")
    )
    study.protocols.append(extraction_protocol)
    sequencing_protocol = Protocol(
        name="sequencing", protocol_type=OntologyAnnotation(term="material sequencing")
    )
    study.protocols.append(sequencing_protocol)

    # To build out assay graphs, we enumereate the samples from the study-level, and for each sample we create an
    # extraction process and a sequencing process. The extraction process takes as input a sample material, and produces
    # an extract material. The sequencing process takes the extract material and produces a data file. This will
    # produce three graphs, from sample material through to data, as follows:
    #
    # (sample_material-0)->(extraction)->(extract-0)->(sequencing)->(sequenced-data-0)
    # (sample_material-1)->(extraction)->(extract-1)->(sequencing)->(sequenced-data-1)
    # (sample_material-2)->(extraction)->(extract-2)->(sequencing)->(sequenced-data-2)
    #
    # Note that the extraction processes and sequencing processes are distinctly separate instances, where the three
    # graphs are NOT interconnected.

    for i, sample in enumerate(study.samples):

        # create an extraction process that executes the extraction protocol

        extraction_process = Process(executes_protocol=extraction_protocol)

        # extraction process takes as input a sample, and produces an extract material as output

        extraction_process.inputs.append(sample)
        material = Material(name="extract-{}".format(i))
        material.type = "Extract Name"
        extraction_process.outputs.append(material)

        # create a sequencing process that executes the sequencing protocol

        sequencing_process = Process(executes_protocol=sequencing_protocol)
        sequencing_process.name = "assay-name-{}".format(i)
        sequencing_process.inputs.append(extraction_process.outputs[0])

        # Sequencing process usually has an output data file

        datafile = DataFile(
            filename="sequenced-data-{}".format(i),
            label="Raw Data File",
            generated_from=[sample],
        )
        sequencing_process.outputs.append(datafile)

        # Ensure Processes are linked forward and backward. plink(from_process, to_process) is a function to set
        # these links for you. It is found in the isatools.model package

        plink(extraction_process, sequencing_process)

        # make sure the extract, data file, and the processes are attached to the assay

        assay.samples.append(sample)
        assay.data_files.append(datafile)
        assay.other_material.append(material)
        assay.process_sequence.append(extraction_process)
        assay.process_sequence.append(sequencing_process)
        assay.measurement_type = OntologyAnnotation(term="gene sequencing")
        assay.technology_type = OntologyAnnotation(term="nucleotide sequencing")

    # attach the assay to the study

    study.assays.append(assay)

    from isatools import isatab

    isatab.dump(
        investigation, "/tmp/"
    )  # dumps() writes out the ISA as a string representation of the ISA-Tab


def create_isatab_archive(
    inv_fp, target_filename=None, filter_by_measurement=None, ignore_missing_files=True
):
    """Function to create an ISArchive; option to select by assay measurement type

    Example usage:

        >>> create_isatab_archive(open('/path/to/i_investigation.txt', target_filename='isatab.zip')
        >>> create_isatab_archive(open('/path/to/i.txt', filter_by_measurement='transcription profiling')
    """
    if target_filename is None:
        target_filename = os.path.join(os.path.dirname(inv_fp.name), "isatab.zip")
    ISA = isatab.load(inv_fp)

    all_files_in_isatab = []
    found_files = []

    for s in ISA.studies:
        if filter_by_measurement is not None:
            logger.debug("Selecting ", filter_by_measurement)
            selected_assays = [
                a for a in s.assays if a.measurement_type.term == filter_by_measurement
            ]
        else:
            selected_assays = s.assays

        for a in selected_assays:
            all_files_in_isatab += [d.filename for d in a.data_files]
    dirname = os.path.dirname(inv_fp.name)

    for fname in all_files_in_isatab:
        if os.path.isfile(os.path.join(dirname, fname)):
            found_files.append(fname)
    missing_files = [f for f in all_files_in_isatab if f not in found_files]

    if len(missing_files) == 0 or ignore_missing_files:
        logger.debug("Do zip")
        with ZipFile(target_filename, mode="w") as zip_file:
            # use relative dir_name to avoid absolute path on file names
            zip_file.write(inv_fp.name, arcname=os.path.basename(inv_fp.name))

            for s in ISA.studies:
                zip_file.write(os.path.join(dirname, s.filename), arcname=s.filename)

                for a in selected_assays:
                    zip_file.write(
                        os.path.join(dirname, a.filename), arcname=a.filename
                    )
            if not ignore_missing_files:
                for file in all_files_in_isatab:
                    zip_file.write(os.path.join(dirname, file), arcname=file)

            logger.debug(zip_file.namelist())
            return zip_file.namelist()

    else:
        logger.debug("Not zipping")
        logger.debug("Missing: ", missing_files)
        return None
