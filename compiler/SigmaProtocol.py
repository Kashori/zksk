import random, string
from collections import namedtuple
from petlib.ec import EcGroup
from petlib.bn import Bn
from petlib.pack import *
import binascii
import pdb
from hashlib import sha256
from collections import defaultdict

CHAL_LENGTH = Bn(128)

""" Known flaws :
        - Malicious prover can trick proofs :
            - claim knowledge of x1 g1, x1 g2 when in fact we have two distinct secrets
            - by-hand craft a prover x1 g1, x2 g2 (without the get_prover being fed a dict)
            - fix : the use of 1 randomizer per different secrets implies that if 
                under a same challenge, two responses are different then the secrets were different.
                Verifier should check that indeed the responses are the same but GLOBALLY (i.e not just in leaves of the And tree)


        - In a non-interactive proof, if the prover and the verifier use two mathematically equivalent yet syntaxically 
            different expressions (e.g "p1 & p2" and "p2 & p1"), the verification fails because of the get_proof_id routine not aware of
            distributivity and commutativity.

        - Sometimes, we get the group order by g.group.order() but is the returned value of hashtopoint
        always a generator of the group itself, and not a subgroup ?
"""

class SigmaProtocol:
    """
    an interface for sigma protocols.
    """
    def __init__(self, verifierClass, proverClass):
        self.verifierClass = verifierClass
        self.proverClass = proverClass

    def setup(self):
        pass

    def verify(
            self
    ) -> bool:  # a method used to chain SigmaProtocols verifications
        victor = self.verifierClass
        peggy = self.proverClass

        (commitment) = peggy.commit()
        challenge = victor.send_challenge(commitment)
        response = peggy.compute_response(challenge)
        return victor.verify(response)

    def run(self):
        if self.verify():
            print("Verified for {0}".format(self.__class__.__name__))
            return True
        else:
            print("Not verified for {0}".format(self.__class__.__name__))
            return False


class Prover:  
    """
    An abstract interface representing Prover used in sigma protocols
    """
    def __init__(self, generators, secret_names, secret_values, lhs):
        pass

    def commit(self, randomizers_dict=None):
        """
        :param randomizers_dict: an optional dictionnary of random values. Each random values is assigned to each secret name
        :return: a single commitment (of type petlib.bn.Bn) for the whole proof
        """
        pass
    def get_secret_values(self):
        pass
    

    def get_proof_id(self):
        """:return: a descriptor of the Proof with the protocol name and the public info. 
        Does NOT contain the secrets' names.
        """
        return self.proof.get_proof_id()
        
    def compute_response(self, challenge):
        pass

    def get_NI_proof(
            self, message=''
    ):  
        """ Non-interactive proof 
        :param message: a string message.
        :return: a challenge that is a hash of (lhs, commitment, message) and a list of responses. Each response has type petlib.bn.Bn 
        """
        commitment = self.commit()
        message = message.encode()
        protocol = encode(self.get_proof_id())

        # Computing the challenge
        conc = protocol
        conc += encode(commitment)
        conc += message
        myhash = sha256(conc).digest()
        challenge = Bn.from_hex(binascii.hexlify(myhash).decode())
        responses = self.compute_response(challenge)
        return (challenge, responses)






class Verifier:  # The Verifier class is built on an array of generators, an array of secrets'IDs and public info

    def send_challenge(self, commitment, chal_size = 128):
        """
        :param commitment: a petlib.bn.Bn number
        :return: a random challenge smaller than 2**128
        """
        self.commitment = commitment
        self.challenge = chal_randbits(CHAL_LENGTH)

        return self.challenge

    def verify(
            self, response, commitment=None,
            challenge=None):  #Can verify simulations with optional arguments
        """
        verifies this proof
        :param response: the response given by the prover
        :return: a boolean telling whether or not the commitment given by the prover matches the one we obtain by recomputing a commitment from the given challenge and response
        """
        self.response = response
        if commitment is None:
            commitment = self.commitment
        if challenge is None:
            challenge = self.challenge
        if self.check_responses_consistency(response, {}):
            raise Exception("Responses for a same secret name do not match!")
        return (commitment == self.proof.recompute_commitment(challenge, response) )

    def verify_NI(self, challenge, response, message=''):
        """
        verification for the non interactive proof
        :param challenge: the challenge a petlib.bn.Bn instance computed from get_NI_proof method
        :param response: computed from get_NI_proof
        :return: a boolean telling if the proof is verified
        """
        self.response = response
        if self.check_responses_consistency(response, {}):
            raise Exception("Responses for a same secret name do not match!")
        message = message.encode()
        protocol = encode(self.get_proof_id())
        r_guess = self.proof.recompute_commitment(challenge, response)  #We retrieve the commitment using the verification identity
        conc = protocol
        conc += encode(r_guess)
        conc += message
        myhash = sha256(conc).digest()
        return challenge == Bn.from_hex(binascii.hexlify(myhash).decode())

    
    def get_proof_id(self):
        """:return: a descriptor of the Proof with the protocol name and the public info. 
        Does NOT contain the secrets' names.
        """
        return self.proof.get_proof_id()

    def check_responses_consistency(self, response, response_dict):
        print("GAGA",response)
        print(self.secret_names)
        return 1


def check_groups(
        list_of_secret_names, list_of_generators
):  
    """checks that if two secrets are the same, the generators they multiply induce groups of same order
    :param list_of_secret_names: a list of secrets names of type string. 
    :param list_of_generators: a list of generators of type petlib.ec.EcPt.
    """
    # We map the unique secrets to the indices where they appear
    mydict = defaultdict(list)
    for idx, word in enumerate(list_of_secret_names):
        mydict[word].append(idx)

    # Now we use this dictionary to check all the generators related to a particular secret live in the same group
    for word, gen_idx in mydict.items(
    ):  #word is the key, gen_idx is the value = a list of indices
        ref_order = list_of_generators[gen_idx[0]].group.order()

        for index in gen_idx:
            if list_of_generators[index].group.order() != ref_order:
                raise Exception(
                    "A shared secret has generators which yield different group orders : secret",
                    word)

    return True

#Useful for several proofs :

def chal_randbits(bitlength):
    maxi = Bn(2).pow(bitlength)
    return maxi.random()


def get_secret_names(sub_list):
    secrets = []
    [secrets.extend(elem.secret_names.copy()) for elem in sub_list]
    return secrets

def get_generators(sub_list):
    generators = []
    [generators.extend(elem.generators.copy()) for elem in sub_list]
    return generators


def add_Bn_array(arr, modulus):
    """ Tool to sum an array under a modulus 
    """
    if not isinstance(modulus, Bn):
        modulus = Bn(modulus)
    res = Bn(0)
    for elem in arr:
        if not isinstance(elem, Bn):
            elem = Bn(elem)
        res = res.mod_add(elem, modulus)
    return res